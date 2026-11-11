"""Reproducible, isolated comment-bridge build; no automatic trust/proxy edits."""

from __future__ import annotations

import hashlib
import io
import json
import socket
import subprocess
import tarfile
import uuid
from pathlib import Path

from .wechat_research import save_private

COMMIT = "124f044235bc706fe796c043a14ff442a150ae5d"
PROFILE = "comments-20261111-v1"
HASHES = {
    "pkg/scraper/wxchannels/interceptor.go": "8d3776dfaa083a9f3a806944fd652701ea229f07842cc1516291a8bdf32dfc73",
    "pkg/scraper/wxchannels/inject/channels.utils.js": "352a65b0523a49d38237206dfd40181e1b7b5db7a360428e3656f73d1c8ca455",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_source(source: Path) -> None:
    for relative, digest in HASHES.items():
        if sha(source / relative) != digest:
            raise ValueError(
                "Unsupported upstream source: " + relative + "; refusing to patch"
            )
    path = source / "pkg/scraper/wxchannels/interceptor.go"
    code = path.read_text()
    start = code.index(
        '\t\t\t\tif strings.Contains(pathname, "virtual_svg-icons-register.publish") {'
    )
    end = code.index('\t\t\t\tif strings.Contains(pathname, "connect.publish")', start)
    code = (
        code[:start]
        + """\t\t\t\tif strings.Contains(pathname, "virtual_svg-icons-register.publish") {
                    js_script = vcExposeExports(js_script)
                    ctx.SetResponseBody(js_script)
                    return
                }

"""
        + code[end:]
    )
    path.write_text(code)
    helper = Path(__file__).with_name("wechat_compat") / "expose_exports.go.txt"
    (path.parent / "videocut_exports.go").write_text(helper.read_text())
    path = source / "pkg/scraper/wxchannels/inject/channels.utils.js"
    path.write_text(patch_registry(path.read_text()))


def patch_registry(code: str) -> str:
    start = code.index("  WXU.onAPILoaded((variables) => {")
    end = code.index("  WXU.onUtilsLoaded(", start)
    section = code[start:end].replace("          return;\n", "")
    section = section.replace(
        "        const methods = variables[variable];",
        "        const methods = variables[variable];\n"
        '        if (!methods || (typeof methods !== "object" && typeof methods !== "function")) return;',
    )
    return code[:start] + section + code[end:]


def renew_certificate(runtime: Path) -> dict:
    """Generate a new local identity. Does not trust it or remove any old identity."""
    cfgpath = runtime / "config.yaml"
    cfg = json.loads(cfgpath.read_text())
    name = "VideosCut-Channels-" + uuid.uuid4().hex[:12]
    folder = runtime / "certificates" / name
    folder.mkdir(parents=True, mode=0o700)
    conf = folder / "openssl.cnf"
    conf.write_text(
        "[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ca\n"
        f"[dn]\nCN={name}\n[ca]\nbasicConstraints=critical,CA:true\n"
        "keyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n"
    )
    cert, key = folder / "ca.pem", folder / "ca.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-config",
            str(conf),
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    key.chmod(0o600)
    cfg["cert"] = {"file": str(cert), "key": str(key), "name": name}
    save_private(cfgpath, cfg)
    return {
        "certificate": str(cert),
        "name": name,
        "trusted_by_this_command": False,
        "note": "New certificate valid for 2 days. Previous certificate files are preserved for cleanup.",
    }


def certificate_status(runtime: Path) -> dict:
    try:
        cfg = json.loads((runtime / "config.yaml").read_text())
        cert, key = cfg["cert"]["file"], cfg["cert"]["key"]
        valid = (
            subprocess.run(
                ["openssl", "x509", "-in", cert, "-checkend", "300", "-noout"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        certpub = subprocess.run(
            ["openssl", "x509", "-in", cert, "-pubkey", "-noout"],
            capture_output=True,
            check=True,
        ).stdout
        keypub = subprocess.run(
            ["openssl", "pkey", "-in", key, "-pubout"], capture_output=True, check=True
        ).stdout
        dates = subprocess.run(
            [
                "openssl",
                "x509",
                "-in",
                cert,
                "-noout",
                "-dates",
                "-fingerprint",
                "-sha1",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {
            "valid_for_next_5_minutes": valid,
            "key_matches": certpub == keypub,
            "certificate": cert,
            "details": dates,
            "system_trust": "not_checked",
        }
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
        return {
            "valid_for_next_5_minutes": False,
            "key_matches": False,
            "error": "Missing/invalid certificate or key; run service-renew-cert",
        }


def prepare(source: Path, runtime: Path, upstream_proxy: str = "") -> dict:
    source, runtime = source.resolve(), runtime.resolve()
    if runtime.exists() and any(runtime.iterdir()):
        raise ValueError(
            "Runtime is not empty; reuse service-run or choose a new runtime"
        )
    # Archive the known commit, never mutate or build the caller\'s dirty checkout.
    archive = subprocess.run(
        ["git", "-C", str(source), "archive", "--format=tar", COMMIT],
        capture_output=True,
        check=True,
    ).stdout
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    checkout = runtime / "source"
    checkout.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(checkout, filter="data")
    patch_source(checkout)
    subprocess.run(
        [
            "gofmt",
            "-w",
            "pkg/scraper/wxchannels/interceptor.go",
            "pkg/scraper/wxchannels/videocut_exports.go",
        ],
        cwd=checkout,
        check=True,
    )
    subprocess.run(
        ["node", "--check", "pkg/scraper/wxchannels/inject/channels.utils.js"],
        cwd=checkout,
        check=True,
    )
    binary = runtime / "wx_video_download"
    subprocess.run(
        [
            "go",
            "build",
            "-mod=mod",
            "-tags",
            "embed_inject,sqlite_only,embed_frontend_inject",
            "-ldflags",
            "-X main.Mode=release -X main.AppVer=" + PROFILE,
            "-o",
            str(binary),
            ".",
        ],
        cwd=checkout,
        check=True,
    )
    config = {
        "workdir": str(runtime / "data"),
        "download": {
            "dir": str(runtime / "downloads"),
            "playDoneAudio": False,
            "maxRunning": 1,
        },
        "api": {"hostname": "127.0.0.1", "port": 2022},
        "proxy": {
            "enabled": True,
            "system": False,
            "hostname": "127.0.0.1",
            "port": 2023,
            "tun": False,
            "upstreamProxy": upstream_proxy,
            "skipInstallRootCert": True,
        },
        "channels": {"download": {"defaultHighest": False, "frontend": False}},
        "mp": {"enabled": False},
        "mcp": {"enabled": False},
    }
    save_private(
        runtime / "config.yaml", config
    )  # JSON is valid YAML; no YAML dependency.
    manifest = {
        "upstream_commit": COMMIT,
        "profile": PROFILE,
        "binary_sha256": sha(binary),
        "binary": str(binary),
        "purpose": "Account search, feeds and comments only; download capture hooks disabled",
        "source": str(checkout),
    }
    save_private(runtime / "build.json", manifest)
    cert = renew_certificate(runtime)
    return {**manifest, **cert, "config": str(runtime / "config.yaml")}


def run_service(runtime: Path) -> int:
    runtime = runtime.resolve()
    manifest = json.loads((runtime / "build.json").read_text())
    binary = runtime / "wx_video_download"
    if manifest.get("profile") != PROFILE or sha(binary) != manifest.get(
        "binary_sha256"
    ):
        raise ValueError("Runtime binary/profile does not match the recorded build")
    status = certificate_status(runtime)
    if not status["valid_for_next_5_minutes"] or not status["key_matches"]:
        raise ValueError(
            "Certificate expired, missing or mismatched; run service-renew-cert first"
        )
    cfg = json.loads((runtime / "config.yaml").read_text())
    if (
        cfg["proxy"].get("system") is not False
        or cfg["proxy"].get("skipInstallRootCert") is not True
    ):
        raise ValueError(
            "Service config must disable automatic system proxy and certificate installation"
        )
    for section in ["api", "proxy"]:
        if cfg[section].get("hostname") != "127.0.0.1":
            raise ValueError("Service must bind to 127.0.0.1")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", int(cfg[section]["port"])))
    try:
        return subprocess.call(
            [str(binary), "--config", str(runtime / "config.yaml")], cwd=runtime
        )
    except KeyboardInterrupt:
        return 130

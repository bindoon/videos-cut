import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from videocut.downloads import DownloadFailure
from videocut.wechat_downloads import WeChatClient
from videocut.wechat_research import Collector, api_data, search
from videocut.wechat_service import certificate_status, renew_certificate


def c(cid, **kw):
    return {"commentId": cid, "username": "user-" + cid, "content": "text " + cid, **kw}


@pytest.fixture
def bridge():
    state = {
        "calls": [],
        "reply_failure": False,
        "cycle": False,
        "bad_envelope": False,
        "bad_flag": False,
        "redirect": False,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            p = urlsplit(self.path)
            q = {k: v[0] for k, v in parse_qs(p.query).items()}
            state["calls"].append((p.path, q))
            if state["redirect"]:
                self.send_response(302)
                self.send_header("Location", "https://example.invalid/credential")
                self.end_headers()
                return
            if p.path.endswith("/contact/search"):
                data = {
                    "infoList": [
                        {
                            "contact": {
                                "username": "target",
                                "nickname": "name",
                                "secret": "discard",
                            }
                        }
                    ],
                    "continueFlag": 0,
                    "lastBuff": "",
                }
            elif p.path.endswith("/contact/feed/list"):
                data = {
                    "object": [
                        {
                            "id": "v1",
                            "objectNonceId": "nonce",
                            "objectDesc": {
                                "description": "video",
                                "media": [
                                    {"urlToken": "SECRET", "decodeKey": "SECRET"}
                                ],
                            },
                        }
                    ],
                    "continueFlag": 0,
                }
            elif q.get("comment_id"):
                if state["reply_failure"]:
                    body = {"code": 0, "data": {"errCode": 7, "errMsg": "SECRET"}}
                    return self.reply(body)
                data = {"commentInfo": [c("r1"), c("r2")], "downContinueFlag": 0}
            elif q.get("next_marker"):
                data = {
                    "commentInfo": [c("c2")],
                    "downContinueFlag": 1 if state["cycle"] else 0,
                    "lastBuffer": "next",
                }
            else:
                data = {
                    "commentInfo": [
                        c(
                            "c1",
                            expandCommentCount=2,
                            continueFlag=1,
                            levelTwoComment=[c("r1")],
                        )
                    ],
                    "downContinueFlag": 1,
                    "lastBuffer": "next",
                }
            if state["bad_flag"]:
                data.pop("downContinueFlag", None)
            body = {"code": 0, "data": {"errCode": 0, "data": data}}
            if state["bad_envelope"]:
                body = {"code": 0, "data": {"errCode": 4, "errMsg": "SECRET"}}
            self.reply(body)

        def reply(self, body):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield WeChatClient(f"http://127.0.0.1:{server.server_port}"), state
    server.shutdown()
    server.server_close()
    thread.join()


def test_pagination_reply_dedup_resume_and_no_media_secrets(
    bridge, tmp_path, monkeypatch
):
    client, state = bridge
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    report = Collector(client, tmp_path, delay=0).collect("target")
    assert report["complete"] and report["comment_count"] == 4
    video = report["videos"][0]
    assert video["root_count"] == 2 and video["replies_complete"]
    assert {c["id"]: c["parent_id"] for c in video["comments"]} == {
        "c1": None,
        "c2": None,
        "r1": "c1",
        "r2": "c1",
    }
    assert "SECRET" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))
    state["calls"].clear()
    again = Collector(client, tmp_path, delay=0).collect("target")
    assert again["complete"] and again["cached_pages"] == 4 and state["calls"] == []
    with pytest.raises(ValueError, match="different account"):
        Collector(client, tmp_path, delay=0).collect("other")


def test_failed_reply_is_partial_and_only_failed_page_retries(
    bridge, tmp_path, monkeypatch
):
    client, state = bridge
    monkeypatch.setattr("videocut.wechat_research.time.sleep", lambda _: None)
    state["reply_failure"] = True
    result = Collector(client, tmp_path, delay=0).collect("target")
    assert not result["complete"] and result["videos"][0]["root_complete"]
    assert not result["videos"][0]["replies_complete"]
    assert result["comment_count"] == 3  # preview retained, no invented fourth comment
    assert "SECRET" not in json.dumps(result)
    state["reply_failure"] = False
    state["calls"].clear()
    result = Collector(client, tmp_path, delay=0).collect("target")
    assert result["complete"] and result["comment_count"] == 4
    assert len(state["calls"]) == 1


@pytest.mark.parametrize(
    "mode,error", [("cycle", "PAGINATION_STALLED"), ("bad_flag", "INVALID_PAGE_DATA")]
)
def test_pagination_cannot_claim_complete(bridge, tmp_path, mode, error):
    client, state = bridge
    state[mode] = True
    result = Collector(client, tmp_path, delay=0).collect("target")
    assert not result["complete"] and error in result["videos"][0]["errors"]


def test_page_limit_is_partial(bridge, tmp_path):
    result = Collector(bridge[0], tmp_path, max_pages=1, delay=0).collect("target")
    assert (
        not result["complete"] and "PAGE_LIMIT_REACHED" in result["videos"][0]["errors"]
    )


def test_search_checks_inner_errors_and_denies_redirects(bridge):
    client, state = bridge
    assert search(client, "name")["accounts"] == [
        {"username": "target", "nickname": "name"}
    ]
    state["bad_envelope"] = True
    with pytest.raises(DownloadFailure) as error:
        api_data(client, "contact/search", {})
    assert error.value.code == "WECHAT_BRIDGE_ERROR" and "SECRET" not in str(
        error.value
    )
    state["redirect"] = True
    with pytest.raises(DownloadFailure, match="redirected"):
        search(client, "name")


def test_cert_rotation_retains_old_identity_and_detects_key_mismatch(tmp_path):
    if not shutil.which("openssl"):
        pytest.skip("openssl not installed")
    (tmp_path / "config.yaml").write_text("{}")
    first = renew_certificate(tmp_path)
    assert certificate_status(tmp_path)["valid_for_next_5_minutes"]
    second = renew_certificate(tmp_path)
    assert Path(first["certificate"]).exists() and first["name"] != second["name"]
    cfg = json.loads((tmp_path / "config.yaml").read_text())
    cfg["cert"]["key"] = str(Path(first["certificate"]).with_name("ca.key"))
    (tmp_path / "config.yaml").write_text(json.dumps(cfg))
    assert not certificate_status(tmp_path)["key_matches"]


def test_export_exposure_preserves_nested_methods_and_dollar_identifiers(tmp_path):
    if not shutil.which("go") or not shutil.which("node"):
        pytest.skip("Go and Node required")
    from videocut import wechat_service

    helper = (
        Path(wechat_service.__file__).with_name("wechat_compat")
        / "expose_exports.go.txt"
    )
    (tmp_path / "helper.go").write_text(
        helper.read_text().replace("package wxchannels", "package main", 1)
    )
    (tmp_path / "main.go").write_text(
        'package main\nimport("fmt";"os")\nfunc main(){b,_:=os.ReadFile(os.Args[1]);fmt.Print(vcExposeExports(string(b)))}'
    )
    script = "const $api={async finderSearch(){if(true){return {data:{nested:1}}}}};export{$api as a};"
    inp = tmp_path / "input.mjs"
    inp.write_text(script)
    result = subprocess.run(
        ["go", "run", "main.go", "helper.go", str(inp)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert script.split("export{")[0] in result and "{$api}" in result
    patched = tmp_path / "patched.mjs"
    patched.write_text(result)
    subprocess.run(["node", "--check", str(patched)], check=True, capture_output=True)
    runner = 'globalThis.WXU={emit:(e,v)=>{globalThis.api=v.$api}};await import("./patched.mjs");if((await api.finderSearch()).data.nested!==1)throw Error("changed behavior");'
    subprocess.run(
        ["node", "--input-type=module", "-e", runner],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    inp.write_text('export{x} from "other";')
    unknown = subprocess.run(
        ["go", "run", "main.go", "helper.go", str(inp)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert unknown == inp.read_text()  # unsupported shape leaves page intact


def test_combined_api_export_registers_all_interfaces_and_ignores_null():
    if not shutil.which("node"):
        pytest.skip("Node required")
    from videocut.wechat_service import patch_registry

    registrations = [
        ("finderGetFollowList", "follow"),
        ("finderGetCommentDetail", "detail"),
        ("finderSearch", "search"),
        ("finderLiveUserPage", "live"),
    ]
    branches = "".join(
        f'if (typeof methods.{method} === "function") {{\n'
        f"          found.{key} = methods;\n          return;\n        }}\n"
        for method, key in registrations
    )
    code = (
        """  WXU.onAPILoaded((variables) => {
    for (const variable of Object.keys(variables)) {
      (() => {
        const methods = variables[variable];
"""
        + branches
        + """      })();
    }
  });
  WXU.onUtilsLoaded(() => {});
"""
    )
    js = "let callback;const found={};const WXU={onAPILoaded:f=>callback=f,onUtilsLoaded(){}};"
    js += patch_registry(code)
    js += (
        "const merged={"
        + ",".join(method + "(){}" for method, _ in registrations)
        + "};"
    )
    js += 'callback({nothing:null,scalar:1,merged});if(Object.keys(found).length!==4)throw Error("missing API");'
    subprocess.run(["node", "-e", js], check=True, capture_output=True)


def test_unknown_upstream_is_rejected_without_modification(tmp_path):
    from videocut.wechat_service import HASHES, patch_source

    for relative in HASHES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("unknown upstream code")
    with pytest.raises(ValueError, match="Unsupported upstream"):
        patch_source(tmp_path)
    assert all(
        (tmp_path / relative).read_text() == "unknown upstream code"
        for relative in HASHES
    )


def test_corrupt_page_cache_is_refetched(bridge, tmp_path):
    client, state = bridge
    assert Collector(client, tmp_path, delay=0).collect("target")["complete"]
    path = next((tmp_path / "pages").glob("*.json"))
    cached = json.loads(path.read_text())
    cached["page"]["items"] = []
    path.write_text(json.dumps(cached))
    state["calls"].clear()
    result = Collector(client, tmp_path, delay=0).collect("target")
    assert result["complete"] and result["comment_count"] == 4
    assert len(state["calls"]) == 1

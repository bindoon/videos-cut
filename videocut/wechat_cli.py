"""CLI for read-only audience research and the isolated compatibility runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .downloads import DownloadFailure
from .wechat_downloads import WeChatClient
from .wechat_research import Collector, search


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="videocut wechat",
        description="WeChat Channels research via a local bridge",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["doctor", "search", "collect"]:
        p = sub.add_parser(name)
        p.add_argument("--api", default="http://127.0.0.1:2022")
        if name == "doctor":
            p.add_argument("--runtime", type=Path)
            p.add_argument(
                "--keyword", help="Also test account-search bridge with this keyword"
            )
        elif name == "search":
            p.add_argument("keyword")
            p.add_argument("--next-marker", default="")
        else:
            p.add_argument(
                "--username",
                required=True,
                help="Explicit account username from search",
            )
            p.add_argument("--output", required=True, type=Path)
            p.add_argument(
                "--max-pages",
                default=1000,
                type=int,
                help="Per root/reply/feed list; reaching limit is incomplete",
            )
    for name in ["service-prepare", "service-run", "service-renew-cert"]:
        p = sub.add_parser(name)
        p.add_argument("--runtime", type=Path, default=Path("upstream/wechat-channels"))
        if name == "service-prepare":
            p.add_argument(
                "--source",
                type=Path,
                required=True,
                help="Local upstream Git checkout containing the pinned commit",
            )
            p.add_argument("--upstream-proxy", default="")
    args = parser.parse_args(argv)
    try:
        if args.command.startswith("service-"):
            from .wechat_service import prepare, renew_certificate, run_service

            if args.command == "service-run":
                return run_service(args.runtime)
            result = (
                prepare(args.source, args.runtime, args.upstream_proxy)
                if args.command == "service-prepare"
                else renew_certificate(args.runtime.resolve())
            )
        else:
            client = WeChatClient(args.api, timeout=40)
            if args.command == "doctor":
                result = {"api": client.origin, "available": False}
                if args.runtime:
                    from .wechat_service import certificate_status

                    result["certificate"] = certificate_status(args.runtime)
                try:
                    result["available"] = (
                        client.request("/api/channels/status").get("available") is True
                    )
                    if args.keyword and result["available"]:
                        result["search"] = search(client, args.keyword)
                    result["bridge_tested"] = bool(args.keyword and result["available"])
                except DownloadFailure as exc:
                    result.update(error=exc.code, message=str(exc))
                cert = result.get("certificate", {})
                ok = (
                    result["available"]
                    and "error" not in result
                    and (
                        not args.runtime
                        or cert.get("valid_for_next_5_minutes")
                        and cert.get("key_matches")
                    )
                )
                result["ready"] = bool(ok)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if ok else 1
            if args.command == "search":
                result = search(client, args.keyword, args.next_marker)
            else:
                report = Collector(
                    client, args.output, max_pages=args.max_pages
                ).collect(args.username)
                result = {k: v for k, v in report.items() if k != "videos"}
                result["report"] = str((args.output / "collection.json").resolve())
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if report["complete"] else 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (
        DownloadFailure,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        # Never print backend response bodies, signed URLs or shell stdout/stderr.
        if isinstance(exc, subprocess.SubprocessError):
            message = (
                "External build/certificate command failed; inspect local tool output"
            )
        else:
            message = str(exc)
        print(
            json.dumps(
                {"error": getattr(exc, "code", type(exc).__name__), "message": message},
                ensure_ascii=False,
            )
        )
        return 1

"""Acceptance checks for the agreed download workflow, using real HTTP and FFmpeg."""

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from videocut.media import run


@pytest.fixture
def source_server(tmp_path):
    video = tmp_path / "sample.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=270x480:rate=24:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(video),
        ]
    )
    content = video.read_bytes()
    state = {
        "requests": [],
        "interrupted": False,
        "payloads": {},
        "slow_started": threading.Event(),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"].append((self.path, self.headers.get("Range")))
            if self.path.startswith("/missing"):
                self.send_error(404)
                return
            if self.path == "/playlist":
                body = b'<html><title>Two films</title><video controls src="/one.mp4"></video><video controls src="/two.mp4"></video></html>'
                mime = "text/html"
            elif self.path.endswith("/page"):
                body = b'<html><title>Sample film</title><video controls src="/sample.mp4"><track kind="subtitles" srclang="en" src="/captions.vtt"></video></html>'
                mime = "text/html"
            elif self.path == "/captions.vtt":
                body = b"WEBVTT\n\n00:00.000 --> 00:01.800\nAn actual subtitle.\n"
                mime = "text/vtt"
            elif self.path in state["payloads"]:
                body, mime = state["payloads"][self.path], "video/mp4"
            else:
                body, mime = content, "video/mp4"
            offset = int(
                self.headers.get("Range", "bytes=0-").split("=")[-1].split("-")[0]
            )
            self.send_response(206 if offset else 200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body) - offset))
            self.send_header("ETag", '"stable-source"')
            if offset:
                self.send_header(
                    "Content-Range", f"bytes {offset}-{len(body) - 1}/{len(body)}"
                )
            self.end_headers()
            if self.path == "/slow.mp4" and not state["slow_started"].is_set():
                import time

                self.wfile.write(body[: len(body) // 2])
                self.wfile.flush()
                state["slow_started"].set()
                time.sleep(0.8)
                try:
                    self.wfile.write(body[len(body) // 2 :])
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            if self.path == "/interrupted.mp4" and not state["interrupted"]:
                state["interrupted"] = True
                self.wfile.write(body[: len(body) // 2])
                self.wfile.flush()
                self.close_connection = True
                return
            self.wfile.write(body[offset:])

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", content, state
    server.shutdown()
    server.server_close()
    thread.join()


def test_direct_resume_and_corrupt_cache_repair(source_server, tmp_path):
    from videocut.downloads import DownloadOptions, download_urls

    base, content, state = source_server
    options = DownloadOptions(retries=1)
    cache = tmp_path / "cache"
    first = download_urls([base + "/interrupted.mp4"], cache, options)
    assert not first["failed"]
    item = first["materials"][0]
    assert Path(item["path"]).read_bytes() == content
    assert any(
        path == "/interrupted.mp4" and offset for path, offset in state["requests"]
    )
    calls = len(state["requests"])
    second = download_urls([base + "/interrupted.mp4"], cache, options)
    assert second["results"][0]["status"] == "cached"
    assert len(state["requests"]) == calls
    Path(item["path"]).write_bytes(b"x" * len(content))
    repaired = download_urls([base + "/interrupted.mp4"], cache, options)
    assert not repaired["failed"]
    assert Path(repaired["materials"][0]["path"]).read_bytes() == content


@pytest.fixture
def wechat_server(source_server):
    """Real HTTP contract double; /play supplies already-decrypted FFmpeg media."""
    import urllib.parse

    _, content, _ = source_server
    state = {
        "available": True,
        "requests": [],
        "payload": content,
        "profile_id": "123",
        "width": 270,
        "height": 480,
        "captures": True,
        "history_url": "unrelated",
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/api/browse_history/list"
            assert body["platform_id"] == "wxchannels"
            self.reply(
                {
                    "list": [
                        {
                            "platform_id": "wxchannels",
                            "external_id": "123",
                            "title": "Captured cotton",
                            "url": state["history_url"],
                            "source_url": "",
                            "extra_data": json.dumps(
                                {"id": "123", "nonce_id": "nonce"}
                            ),
                            "accounts": [{"nickname": "Creator"}],
                        }
                    ]
                    if state["captures"]
                    else [],
                    "total": int(state["captures"]),
                }
            )

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            state["requests"].append((parsed.path, query))
            if parsed.path == "/api/channels/status":
                self.reply({"available": state["available"]})
            elif parsed.path == "/api/channels/feed/profile":
                assert query == {"oid": ["123"], "nid": ["nonce"]}
                self.reply(
                    {
                        "errCode": 0,
                        "data": {
                            "object": {
                                "id": state["profile_id"],
                                "nickname": "Creator",
                                "objectDesc": {
                                    "description": "Cotton into clothing",
                                    "media": [
                                        {
                                            "mediaType": 4,
                                            "url": "https://finder.video.qq.com/video?encfilekey=secret",
                                            "urlToken": "&token=do-not-persist-cdn-token",
                                            "decodeKey": "123456",
                                            "spec": [
                                                {
                                                    "fileFormat": "xWT111",
                                                    "width": state["width"],
                                                    "height": state["height"],
                                                    "codingFormat": "h264",
                                                }
                                            ],
                                        }
                                    ],
                                },
                            }
                        },
                    }
                )
            elif parsed.path == "/play":
                assert query["key"] == ["123456"]
                remote = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(query["url"][0]).query
                )
                assert remote["X-snsvideoflag"] == ["xWT111"]
                self.send_response(200)
                self.send_header("Content-Length", str(len(state["payload"])))
                self.end_headers()
                self.wfile.write(state["payload"])
            else:
                self.send_error(404)

        def reply(self, data):
            raw = json.dumps({"code": 0, "data": data}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", content, state
    server.shutdown()
    server.server_close()
    thread.join()


WECHAT_URL = "https://weixin.qq.com/sph/example"


def test_wechat_download_cache_repair_and_secret_free_report(wechat_server, tmp_path):
    from videocut.downloads import DownloadOptions, download_urls

    base, content, state = wechat_server
    # A broken outbound proxy must never receive local control/decryption calls.
    options = DownloadOptions(
        wechat_api=base,
        wechat_feed_id="123",
        proxy="http://127.0.0.1:1",
        subtitles=True,
    )
    output = tmp_path / "job"
    first = download_urls([WECHAT_URL], tmp_path / "cache", options, output=output)
    assert not first["failed"], first["results"]
    material = first["materials"][0]
    assert Path(material["path"]).read_bytes() == content
    assert material["platform"] == "wechat" and material["source_id"] == "123"
    assert material["credit"] == "Creator" and material["wechat_spec"] == "xWT111"
    assert material["subtitles"] == [] and material["url"] == WECHAT_URL
    assert material["sha256"] == hashlib.sha256(content).hexdigest()
    report = json.dumps(first)
    assert all(
        secret not in report
        for secret in ["encfilekey", "123456", "do-not-persist-cdn-token", "/play?"]
    )
    assert not list((tmp_path / "cache").rglob("*.part.json"))
    state["available"] = False
    state["requests"].clear()
    cached = download_urls([WECHAT_URL], tmp_path / "cache", options)
    assert cached["results"][0]["status"] == "cached" and not state["requests"]
    state["available"] = True
    Path(material["path"]).write_bytes(b"x" * len(content))
    fixed = download_urls([WECHAT_URL], tmp_path / "cache", options)
    assert (
        not fixed["failed"]
        and Path(fixed["materials"][0]["path"]).read_bytes() == content
    )


def test_wechat_never_guesses_recent_video_and_checks_identity(wechat_server, tmp_path):
    from videocut.downloads import DownloadOptions, download_urls

    base, _, state = wechat_server

    def attempt(**kw):
        return download_urls(
            [WECHAT_URL], tmp_path / "cache", DownloadOptions(wechat_api=base, **kw)
        )

    failed = attempt()
    assert failed["results"][0]["error"]["code"] == "WECHAT_CAPTURE_REQUIRED"
    assert not any(path == "/play" for path, _ in state["requests"])
    state["profile_id"] = "999"
    failed = attempt(wechat_feed_id="123")
    assert failed["results"][0]["error"]["code"] == "WECHAT_PROFILE_ERROR"
    state["available"] = False
    assert attempt()["results"][0]["error"]["code"] == "WECHAT_PAGE_REQUIRED"


@pytest.mark.parametrize("failure", ["size", "corrupt", "resolution"])
def test_wechat_budgets_decryption_and_resolution_are_enforced(
    wechat_server, tmp_path, failure
):
    from videocut.downloads import DownloadOptions, download_urls

    base, _, state = wechat_server
    options = {"wechat_api": base, "wechat_feed_id": "123"}
    if failure == "size":
        options["max_bytes"] = 1
    elif failure == "corrupt":
        state["payload"] = b"encrypted or invalid video"
    else:
        state["width"], state["height"] = 720, 1280
    r = download_urls([WECHAT_URL], tmp_path / "cache", DownloadOptions(**options))
    assert r["failed"] == 1 and not r["materials"]
    assert (
        r["results"][0]["error"]["code"]
        == {
            "size": "SIZE_LIMIT",
            "corrupt": "INVALID_MEDIA",
            "resolution": "FORMAT_UNAVAILABLE",
        }[failure]
    )


def test_wechat_audio_catalog_and_exact_url_match(wechat_server, tmp_path):
    from videocut.assets import import_catalog_items
    from videocut.downloads import DownloadOptions, download_urls

    base, _, state = wechat_server
    r = import_catalog_items(
        [
            {
                "url": WECHAT_URL,
                "source": "wechat",
                "wechat_feed_id": "123",
                "kind": "music",
                "tags": ["cotton"],
            }
        ],
        tmp_path / "cache",
        DownloadOptions(wechat_api=base),
    )
    assert not r["failed"], r["results"]
    assert r["materials"][0]["kind"] == "music" and r["materials"][0]["tags"] == [
        "cotton"
    ]
    assert all(s["codec_type"] == "audio" for s in r["materials"][0]["streams"])
    state["history_url"] = WECHAT_URL
    r = download_urls(
        [WECHAT_URL], tmp_path / "other", DownloadOptions(wechat_api=base)
    )
    assert not r["failed"], r["results"]


def test_wechat_formats_and_loopback_boundary():
    from videocut.downloads import DownloadFailure, DownloadOptions
    from videocut.wechat_downloads import select_spec

    specs = {
        "spec": [
            {
                "fileFormat": "small",
                "width": 360,
                "height": 640,
                "codingFormat": "h264",
            },
            {
                "fileFormat": "hevc",
                "width": 720,
                "height": 1280,
                "codingFormat": "h265",
            },
            {
                "fileFormat": "h264",
                "width": 720,
                "height": 1280,
                "codingFormat": "h264",
            },
            {
                "fileFormat": "large",
                "width": 1080,
                "height": 1920,
                "codingFormat": "h265",
            },
        ]
    }
    assert select_spec(specs, "preview")["fileFormat"] == "small"
    assert select_spec(specs, "edit")["fileFormat"] == "h264"
    assert select_spec(specs, "source")["fileFormat"] == "large"
    with pytest.raises(DownloadFailure, match="No explicit"):
        select_spec({"spec": []}, "source")
    for endpoint in [
        "http://example.com:2022",
        "http://127.0.0.1:2022/path",
        "http://secret@localhost:2022",
        "http://localhost:0",
    ]:
        with pytest.raises(ValueError, match="loopback"):
            DownloadOptions(wechat_api=endpoint)


def test_wechat_detail_url_does_not_require_history_and_offline_failure_is_actionable(
    wechat_server, tmp_path
):
    import socket

    from videocut.downloads import DownloadOptions, download_urls

    base, _, state = wechat_server
    state["captures"] = False
    detail = "https://channels.weixin.qq.com/web/pages/feed?oid=123&nid=nonce"
    r = download_urls([detail], tmp_path / "cache", DownloadOptions(wechat_api=base))
    assert not r["failed"], r["results"]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    offline = download_urls(
        [WECHAT_URL],
        tmp_path / "other",
        DownloadOptions(wechat_api=f"http://127.0.0.1:{port}", wechat_feed_id="123"),
    )
    assert offline["results"][0]["error"]["code"] == "WECHAT_SERVICE_UNAVAILABLE"


def test_wechat_cli_listing_retry_and_mixed_batch(
    wechat_server, source_server, tmp_path
):
    import subprocess
    import sys

    from videocut.downloads import DownloadOptions, download_urls

    base, _, state = wechat_server
    listed = subprocess.run(
        [
            sys.executable,
            "-m",
            "videocut",
            "download",
            "--wechat-list",
            "--wechat-api",
            base,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout)["videos"][0]["feed_id"] == "123"
    state["history_url"] = WECHAT_URL
    state["available"] = False
    output = tmp_path / "batch"
    r = download_urls(
        [source_server[0] + "/sample.mp4", WECHAT_URL],
        tmp_path / "cache",
        DownloadOptions(wechat_api=base),
        output=output,
    )
    assert r["failed"] == 1 and len(r["materials"]) == 1
    state["available"] = True
    retried = subprocess.run(
        [
            sys.executable,
            "-m",
            "videocut",
            "download",
            "--retry-failed",
            str(output / "download-report.json"),
            "--output",
            str(tmp_path / "retry"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert retried.returncode == 0, retried.stdout + retried.stderr
    material = json.loads((tmp_path / "retry/materials.json").read_text())[0]
    assert material["platform"] == "wechat"


def test_web_video_audio_and_subtitles_are_separate_variants(source_server, tmp_path):
    pytest.importorskip("yt_dlp")
    from videocut.downloads import DownloadOptions, download_urls

    base, _, _ = source_server
    cache = tmp_path / "cache"
    video = download_urls(
        [base + "/page"], cache, DownloadOptions(subtitles=True, quality="preview")
    )
    assert not video["failed"], video["results"]
    item = video["materials"][0]
    assert item["kind"] == "video"
    assert any(s["codec_type"] == "video" for s in item["streams"])
    assert item["subtitles"]
    assert "An actual subtitle" in Path(item["subtitles"][0]["path"]).read_text()
    audio = download_urls([base + "/page"], cache, DownloadOptions(mode="audio"))
    assert not audio["failed"]
    audio_item = audio["materials"][0]
    assert audio_item["path"] != item["path"]
    assert audio_item["kind"] == "music"
    assert all(s["codec_type"] == "audio" for s in audio_item["streams"])


def test_generic_page_ids_are_isolated_by_origin_url(source_server, tmp_path):
    pytest.importorskip("yt_dlp")
    from videocut.downloads import download_urls

    base, _, _ = source_server
    report = download_urls([base + "/one/page", base + "/two/page"], tmp_path / "cache")
    assert not report["failed"], report["results"]
    assert len({m["id"] for m in report["materials"]}) == 2
    assert len({m["path"] for m in report["materials"]}) == 2


def test_invalid_payload_is_not_registered_and_retry_can_recover(
    source_server, tmp_path
):
    from videocut.downloads import download_urls

    base, content, state = source_server
    state["payloads"]["/flaky.mp4"] = b"<html>No video</html>"
    first = download_urls([base + "/flaky.mp4"], tmp_path / "cache")
    assert not first["materials"] and first["failed"] == 1
    assert first["results"][0]["error"]["code"] == "INVALID_MEDIA"
    state["payloads"]["/flaky.mp4"] = content
    recovered = download_urls([base + "/flaky.mp4"], tmp_path / "cache")
    assert not recovered["failed"]
    assert Path(recovered["materials"][0]["path"]).read_bytes() == content


def test_local_catalog_inputs_are_not_remote_download_budget(source_server, tmp_path):
    from videocut.assets import import_catalog_items
    from videocut.downloads import DownloadOptions

    _, content, _ = source_server
    local = tmp_path / "local.mp4"
    local.write_bytes(content)
    report = import_catalog_items(
        [{"id": "local", "kind": "video", "path": str(local)}],
        tmp_path / "cache",
        DownloadOptions(max_bytes=1, max_total_bytes=1),
    )
    assert not report["failed"]
    assert report["materials"][0]["path"] == str(local.resolve())


def test_batch_failure_does_not_discard_good_material(source_server, tmp_path):
    from videocut.downloads import DownloadOptions, download_urls

    base, _, _ = source_server
    report = download_urls(
        [base + "/sample.mp4", base + "/missing.mp4"],
        tmp_path / "cache",
        DownloadOptions(retries=0),
    )
    assert len(report["materials"]) == 1
    assert report["failed"] == 1
    assert [r["status"] for r in report["results"]] == ["downloaded", "failed"]
    assert report["results"][1]["error"]["code"] == "HTTP_ERROR"


def test_playlist_requires_opt_in_and_respects_item_limit(source_server, tmp_path):
    pytest.importorskip("yt_dlp")
    from videocut.downloads import DownloadOptions, download_urls

    base, _, _ = source_server
    refused = download_urls([base + "/playlist"], tmp_path / "cache", DownloadOptions())
    assert refused["failed"] == 1
    assert refused["results"][0]["error"]["code"] == "PLAYLIST_REQUIRES_FLAG"
    allowed = download_urls(
        [base + "/playlist"],
        tmp_path / "cache",
        DownloadOptions(playlist=True, limit=1),
    )
    assert not allowed["failed"], allowed["results"]
    assert len(allowed["materials"]) == 1


def test_size_limits_never_publish_oversized_material(source_server, tmp_path):
    from videocut.downloads import DownloadOptions, download_urls

    base, content, _ = source_server
    small = download_urls(
        [base + "/sample.mp4"], tmp_path / "small", DownloadOptions(max_bytes=100)
    )
    assert not small["materials"] and small["failed"] == 1
    total = download_urls(
        [base + "/a.mp4", base + "/b.mp4"],
        tmp_path / "total",
        DownloadOptions(max_total_bytes=len(content) + 100),
    )
    assert len(total["materials"]) == 1 and total["failed"] == 1


def test_failed_partial_counts_towards_batch_budget(source_server, tmp_path):
    from videocut.downloads import DownloadOptions, download_urls

    base, content, _ = source_server
    report = download_urls(
        [base + "/interrupted.mp4", base + "/second.mp4"],
        tmp_path / "cache",
        DownloadOptions(retries=0, max_total_bytes=len(content) + 100),
    )
    assert not report["materials"] and report["failed"] == 2
    assert report["results"][1]["error"]["code"] == "TOTAL_SIZE_LIMIT"


def test_existing_catalog_and_same_name_sources_remain_usable(source_server, tmp_path):
    from videocut.assets import download_materials

    base, content, _ = source_server
    catalog = tmp_path / "materials.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "id": "first",
                    "kind": "video",
                    "url": base + "/a.mp4",
                    "filename": "same.mp4",
                    "tags": ["first"],
                },
                {
                    "id": "second",
                    "kind": "video",
                    "url": base + "/b.mp4",
                    "filename": "same.mp4",
                    "tags": ["second"],
                },
            ]
        )
    )
    result = download_materials(catalog, tmp_path / "cache")
    assert len(result) == 2
    assert result[0]["path"] != result[1]["path"]
    assert [r["id"] for r in result] == ["first", "second"]
    assert result[0]["sha256"] == hashlib.sha256(content).hexdigest()


def test_failure_report_can_be_retried_from_cli(source_server, tmp_path):
    import subprocess
    import sys

    base, _, _ = source_server
    output = tmp_path / "job"
    command = [
        sys.executable,
        "-m",
        "videocut",
        "download",
        base + "/sample.mp4",
        base + "/missing.mp4",
        "--cache",
        str(tmp_path / "cache"),
        "--output",
        str(output),
        "--retries",
        "0",
    ]
    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 1
    assert len(json.loads((output / "materials.json").read_text())) == 1
    retry = subprocess.run(
        [
            sys.executable,
            "-m",
            "videocut",
            "download",
            "--retry-failed",
            str(output / "download-report.json"),
            "--output",
            str(tmp_path / "retry"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert retry.returncode == 1
    report = json.loads((tmp_path / "retry/download-report.json").read_text())
    assert len(report["results"]) == 1
    assert report["results"][0]["url"].endswith("missing.mp4")


def test_cli_interruption_preserves_partial_and_pending_sources(
    source_server, tmp_path
):
    import signal
    import subprocess
    import sys
    import time

    base, _, state = source_server
    output = tmp_path / "job"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "videocut",
            "download",
            base + "/slow.mp4",
            base + "/second.mp4",
            "--cache",
            str(tmp_path / "cache"),
            "--output",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert state["slow_started"].wait(10)
        time.sleep(0.1)
        process.send_signal(signal.SIGINT)
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    assert process.returncode != 0
    report = json.loads((output / "download-report.json").read_text())
    assert [r["error"]["code"] for r in report["results"]] == [
        "INTERRUPTED",
        "NOT_ATTEMPTED",
    ]
    assert any(p.stat().st_size > 0 for p in (tmp_path / "cache").rglob("*.part"))
    retry = subprocess.run(
        [
            sys.executable,
            "-m",
            "videocut",
            "download",
            "--retry-failed",
            str(output / "download-report.json"),
            "--output",
            str(tmp_path / "retry"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert retry.returncode == 0, retry.stderr
    assert len(json.loads((tmp_path / "retry/materials.json").read_text())) == 2
    assert any(path == "/slow.mp4" and offset for path, offset in state["requests"])

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

"""Loopback-only review UI. HTTP cannot execute renderers or edit source files."""
from __future__ import annotations

import json
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import review


def create_server(workspace: Path, port: int = 4862) -> ThreadingHTTPServer:
    root = workspace.resolve()
    review.state(root)  # Refuse to serve an uninitialized directory.
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _host(self) -> bool:
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def _send(self, status: int, payload: object, mime: str = "application/json; charset=utf-8") -> None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self._host():
                return self._send(403, {"error": "Invalid host"})
            path = urlparse(self.path).path
            try:
                if path == "/":
                    body = Path(__file__).with_name("review_ui.html").read_text().replace("__REVIEW_TOKEN__", token)
                    return self._send(200, body.encode(), "text/html; charset=utf-8")
                if path == "/api/state":
                    return self._send(200, review.state(root))
                match = re.fullmatch(r"/media/([0-9a-f]{16})\.mp4", path)
                if match:
                    doc = review.revision(root, match[1], media=True)
                    file = root / "revisions" / match[1] / "preview.mp4"
                    size = doc["video"]["bytes"]
                    start, end, status = 0, size - 1, 200
                    value = self.headers.get("Range")
                    if value:
                        found = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
                        if not found or not any(found.groups()):
                            return self._send(416, {"error": "Invalid range"})
                        a, b = found.groups()
                        if a:
                            start, end = int(a), min(int(b) if b else size - 1, size - 1)
                        else:
                            length = int(b)
                            if length <= 0:
                                return self._send(416, {"error": "Invalid suffix range"})
                            start = max(0, size - length)
                        if start >= size or start > end:
                            return self._send(416, {"error": "Unsatisfiable range"})
                        status = 206
                    self.send_response(status)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Disposition", f'inline; filename="preview-v{doc["number"]}.mp4"')
                    if status == 206:
                        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.end_headers()
                    if self.command != "HEAD":
                        with file.open("rb") as stream:
                            stream.seek(start)
                            remaining = end - start + 1
                            while remaining:
                                chunk = stream.read(min(256 * 1024, remaining))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                    return
                return self._send(404, {"error": "Not found"})
            except (BrokenPipeError, ConnectionResetError):
                return
            except (ValueError, OSError, KeyError, RuntimeError) as error:
                return self._send(409, {"error": str(error)})

        def do_POST(self):
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self._host() or self.headers.get("X-Review-Token") != token or self.headers.get("Origin") not in allowed:
                return self._send(403, {"error": "Invalid local review token/origin"})
            if urlparse(self.path).path != "/api/comments":
                return self._send(404, {"error": "Not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 32000:
                    raise ValueError("Comment request too large or empty")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Expected comment object")  # noqa: TRY004 - invalid JSON value, reported as input validation
                result = review.comment(root, revision_id=body.get("revision"), time=body.get("time"),
                                        scene_id=body.get("scene"), region=body.get("region"), text=body.get("text"))
                self._send(201, result)
            except (ValueError, OSError, KeyError, RuntimeError) as error:
                self._send(409, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

"""Import remote media as verified local materials; rendering stays provider-agnostic."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .media import probe, run

MEDIA_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
    ".flac",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}


@dataclasses.dataclass(frozen=True)
class DownloadOptions:
    mode: str = "video"
    quality: str = "edit"
    playlist: bool = False
    limit: int = 20
    max_bytes: int = 1024 * 1024 * 1024
    max_total_bytes: int = 4 * 1024 * 1024 * 1024
    retries: int = 2
    subtitles: bool = False
    sub_langs: str = "zh.*,en.*"
    proxy: str | None = None
    cookies: str | None = None

    def __post_init__(self):
        if self.mode not in {"video", "audio"} or self.quality not in {
            "preview",
            "edit",
            "source",
        }:
            raise ValueError("Invalid download mode or quality")
        if (
            min(self.max_bytes, self.max_total_bytes, self.limit) <= 0
            or self.retries < 0
        ):
            raise ValueError(
                "Download limits must be positive; retries cannot be negative"
            )

    def public(self):
        # Keep credentials out of reports. Retry reads fresh explicit CLI settings.
        return {
            k: v
            for k, v in dataclasses.asdict(self).items()
            if k not in {"cookies", "proxy"}
        }

    def variant(self):
        return {
            k: getattr(self, k) for k in ("mode", "quality", "subtitles", "sub_langs")
        }


class DownloadFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:24]


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def _read_cache_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text())
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


@contextlib.contextmanager
def _lock(path: Path):
    # The local CLI targets macOS/Linux, as do the existing model environments.
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def inspect_material(path: Path, kind: str) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise DownloadFailure("INVALID_MEDIA", f"Empty or missing material: {path}")
    if kind in {"image", "sticker"}:
        from PIL import Image

        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            raise DownloadFailure("INVALID_MEDIA", f"Invalid image: {path}") from exc
        details = {}
    else:
        try:
            info = probe(path)
            streams = info.get("streams", [])
            required = "audio" if kind == "music" else "video"
            if not any(s["codec_type"] == required for s in streams):
                raise ValueError(f"Missing {required} stream")
            seconds = float(info.get("format", {}).get("duration", 0))
            if seconds <= 0:
                raise ValueError("Missing media duration")
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-xerror",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0?",
                    "-map",
                    "0:a:0?",
                    "-f",
                    "null",
                    "-",
                ],
                timeout=max(120, min(3600, int(seconds))),
            )
            details = {
                "duration": seconds,
                "streams": [
                    {
                        k: s[k]
                        for k in (
                            "codec_type",
                            "codec_name",
                            "width",
                            "height",
                            "channels",
                        )
                        if k in s
                    }
                    for s in streams
                ],
            }
        except Exception as exc:
            raise DownloadFailure(
                "INVALID_MEDIA", f"Media verification failed for {path}: {exc}"
            ) from exc
    return {
        "path": str(path.resolve()),
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": checksum(path),
        **details,
    }


def _error(exc: Exception) -> dict:
    if isinstance(exc, DownloadFailure):
        code = exc.code
    elif isinstance(exc, urllib.error.HTTPError):
        code = "RATE_LIMITED" if exc.code == 429 else "HTTP_ERROR"
    else:
        text = str(exc).lower()
        if "unsupported url" in text:
            code = "UNSUPPORTED_URL"
        elif "requested format" in text:
            code = "FORMAT_UNAVAILABLE"
        elif any(
            word in text
            for word in (
                "sign in",
                "login required",
                "log in",
                "cookies",
                "authentication",
            )
        ):
            code = "AUTH_REQUIRED"
        else:
            code = "DOWNLOAD_FAILED"
    return {"code": code, "message": str(exc)[-3000:]}


class Importer:
    def __init__(self, cache: Path, options: DownloadOptions):
        self.cache = cache.resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.options = options
        self.used_bytes = 0
        self.charged_paths: set[str] = set()
        self.retained_bytes: dict[str, int] = {}
        self.last_progress = 0.0

    def _budget(self, size: int):
        if size > self.options.max_bytes:
            raise DownloadFailure(
                "SIZE_LIMIT",
                f"Material exceeds {self.options.max_bytes / 1024**2:g} MiB; increase --max-size-mb",
            )
        if self.used_bytes + size > self.options.max_total_bytes:
            raise DownloadFailure("TOTAL_SIZE_LIMIT", "Batch exceeds --max-total-mb")

    def _clear_retained(self, key: str):
        self.used_bytes -= self.retained_bytes.pop(key, 0)

    def _retain(self, key: str, files):
        self._clear_retained(key)
        size = sum(
            p.stat().st_size
            for p in files
            if p.is_file() and p.suffix not in {".json", ".lock"}
        )
        self.retained_bytes[key] = size
        self.used_bytes += size

    def _claim(self, material: dict):
        if material["path"] not in self.charged_paths:
            self._budget(material["bytes"])
            self.used_bytes += material["bytes"]
            self.charged_paths.add(material["path"])

    def _inspect_download(self, path: Path, kind: str) -> dict:
        try:
            return inspect_material(path, kind)
        except DownloadFailure:
            # Invalid completed filenames must not poison future retries.
            if path.resolve().is_relative_to(self.cache):
                path.unlink(missing_ok=True)
            raise

    def _cached(self, manifest: Path) -> dict | None:
        if not manifest.is_file():
            return None
        try:
            material = json.loads(manifest.read_text())
            files = [material, *material.get("subtitles", [])]
            valid = all(
                Path(f["path"]).is_file()
                and Path(f["path"]).stat().st_size == f["bytes"]
                and checksum(Path(f["path"])) == f["sha256"]
                for f in files
            )
            if valid:
                self._claim(material)
                return material
            for file in files:
                path = Path(file["path"])
                if path.is_relative_to(self.cache):
                    path.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        manifest.unlink(missing_ok=True)
        return None

    def _index(self, url: str, source: str) -> Path:
        return (
            self.cache
            / ".downloads/requests"
            / (_hash([url, source, self.options.variant()]) + ".json")
        )

    def _http(self, url: str, target: Path, referer: str = ""):
        key = str(target)
        self._clear_retained(key)
        try:
            self._http_transfer(url, target, referer)
        except (Exception, KeyboardInterrupt):
            self._retain(key, [target.with_name(target.name + ".part")])
            raise

    def _http_transfer(self, url: str, target: Path, referer: str = ""):
        part = target.with_name(target.name + ".part")
        state = part.with_name(part.name + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(self.options.retries + 1):
            try:
                previous = _read_cache_json(state)
                validator = previous.get("etag") or previous.get("last_modified")
                offset = (
                    part.stat().st_size
                    if part.exists() and previous.get("url") == url and validator
                    else 0
                )
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Referer": referer,
                    "Accept-Encoding": "identity",
                }
                if offset:
                    headers.update({"Range": f"bytes={offset}-", "If-Range": validator})
                request = urllib.request.Request(url, headers=headers)
                handler = (
                    urllib.request.ProxyHandler(
                        {"http": self.options.proxy, "https": self.options.proxy}
                    )
                    if self.options.proxy is not None
                    else urllib.request.ProxyHandler()
                )
                with urllib.request.build_opener(handler).open(
                    request, timeout=30
                ) as response:
                    if response.status != 206:
                        offset = 0
                    elif not response.headers.get("Content-Range", "").startswith(
                        f"bytes {offset}-"
                    ):
                        raise DownloadFailure(
                            "INVALID_RANGE",
                            "Server returned an inconsistent resume range",
                        )
                    if (
                        offset
                        and previous.get("etag")
                        and response.headers.get("ETag") != previous["etag"]
                    ):
                        part.unlink(missing_ok=True)
                        state.unlink(missing_ok=True)
                        raise OSError("Source changed during resume")
                    length = response.headers.get("Content-Length")
                    expected = offset + int(length) if length else None
                    self._budget(expected or offset)
                    atomic_json(
                        state,
                        {
                            "url": url,
                            "etag": response.headers.get("ETag"),
                            "last_modified": response.headers.get("Last-Modified"),
                        },
                    )
                    size = offset
                    with part.open("ab" if offset else "wb") as stream:
                        while chunk := response.read(64 * 1024):
                            self._budget(size + len(chunk))
                            stream.write(chunk)
                            size += len(chunk)
                            self._print_progress(size, expected)
                    if expected is not None and size != expected:
                        raise OSError(f"Incomplete response: {size}/{expected} bytes")
                    if size == 0:
                        raise DownloadFailure(
                            "INVALID_MEDIA", "Empty download response"
                        )
                part.replace(target)
                state.unlink(missing_ok=True)
                return
            except urllib.error.HTTPError as exc:
                if attempt == self.options.retries or exc.code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
            except (OSError, TimeoutError):
                if attempt == self.options.retries:
                    raise
            time.sleep(min(attempt + 1, 3))

    def _print_progress(self, downloaded: int, total: int | None):
        now = time.monotonic()
        if now - self.last_progress > 1:
            suffix = f" / {total / 1024**2:.1f} MiB" if total else " MiB"
            print(f"下载中: {downloaded / 1024**2:.1f}{suffix}", flush=True)
            self.last_progress = now

    def direct(
        self,
        url: str,
        kind: str = "video",
        *,
        preferred: Path | None = None,
        referer: str = "",
    ) -> tuple[dict, str]:
        folder = self.cache / "imports/direct" / _hash([url, self.options.variant()])
        manifest = folder / "material.json"
        with contextlib.ExitStack() as locks:
            locks.enter_context(_lock(folder / ".lock"))
            if preferred is not None:
                locks.enter_context(
                    _lock(self.cache / ".downloads/name-locks" / _hash(str(preferred)))
                )
            if material := self._cached(manifest):
                return material, "cached"
            ext = Path(urllib.parse.urlsplit(url).path).suffix.lower()
            if ext not in MEDIA_EXTENSIONS:
                ext = preferred.suffix if preferred else ".mp4"
            target = folder / ("source" + ext)
            # Preserve legacy catalog filenames, while isolating later same-name URLs.
            if preferred is not None and self.options.mode == "video":
                owner = (
                    self.cache / ".downloads/names" / (_hash(str(preferred)) + ".json")
                )
                if not owner.exists() or _read_cache_json(owner).get("url") == url:
                    target = preferred
                    atomic_json(owner, {"url": url})
            print(f"下载文件: {url}", flush=True)
            if not target.exists():
                self._http(url, target, referer)
            if self.options.mode == "audio":
                raw = probe(target)
                track = next(
                    (s for s in raw["streams"] if s["codec_type"] == "audio"), None
                )
                if not track:
                    raise DownloadFailure("NO_AUDIO", "Source has no audio stream")
                audio = folder / "audio.m4a"
                codec = "copy" if track.get("codec_name") == "aac" else "aac"
                run(
                    [
                        "ffmpeg",
                        "-y",
                        "-v",
                        "error",
                        "-i",
                        str(target),
                        "-vn",
                        "-c:a",
                        codec,
                        str(audio),
                    ]
                )
                target, kind = audio, "music"
            material = {
                "id": "direct-" + _hash(url),
                "kind": kind,
                "url": url,
                "page": url,
                "source": "direct",
                "license": "unknown",
                "tags": [],
                "requested": self.options.variant(),
                **self._inspect_download(target, kind),
            }
            self._claim(material)
            atomic_json(manifest, material)
            return material, "downloaded"

    def _ydl_options(self, folder: Path | None = None) -> dict:
        try:
            import yt_dlp  # noqa: F401
        except ImportError as exc:
            raise DownloadFailure(
                "MISSING_DEPENDENCY",
                "Web downloads need: uv sync --extra download (add --extra asr if using speech recognition)",
            ) from exc
        options = {
            "quiet": True,
            "noprogress": True,
            "no_warnings": False,
            "noplaylist": not self.options.playlist,
            "socket_timeout": 20,
            "retries": self.options.retries,
            "extractor_retries": self.options.retries,
            "fragment_retries": self.options.retries,
            "continuedl": True,
            "max_filesize": self.options.max_bytes,
            "js_runtimes": {"node": {}, "deno": {}},
            "playlistend": self.options.limit,
            "ignoreerrors": False,
            # Extractors such as TikTok fetch caption metadata only when requested.
            "writesubtitles": self.options.subtitles,
            "writeautomaticsub": self.options.subtitles,
            "subtitleslangs": self.options.sub_langs.split(","),
            "subtitlesformat": "srt/vtt/best",
        }
        if self.options.proxy is not None:
            options["proxy"] = self.options.proxy
        if self.options.cookies:
            options["cookiefile"] = self.options.cookies
        if folder:
            height = {"preview": 360, "edit": 720, "source": None}[self.options.quality]
            # Some HTML5 pages expose no resolution until the file is downloaded.
            # Preserve those candidates, then record their measured resolution.
            bounds = [f"[height<=?{height}]", f"[width<=?{height}]"] if height else [""]
            # A 720p portrait video is 720x1280: cap the short edge, not height alone.
            video_formats = [
                f"bestvideo{b}[vcodec~='^(avc1|h264)']+bestaudio" for b in bounds
            ]
            video_formats += [f"best{b}" for b in bounds]
            video_formats += [f"bestvideo{b}+bestaudio" for b in bounds]
            if self.options.quality == "source":
                video_formats = ["bestvideo+bestaudio", "best"]
            options.update(
                {
                    "outtmpl": str(folder / "source.%(ext)s"),
                    "format": "bestaudio/best"
                    if self.options.mode == "audio"
                    else "/".join(video_formats),
                    "merge_output_format": "mp4",
                    "writesubtitles": self.options.subtitles,
                    "writeautomaticsub": self.options.subtitles,
                    "subtitleslangs": self.options.sub_langs.split(","),
                    "subtitlesformat": "srt/vtt/best",
                }
            )

            def progress(data):
                size = sum(
                    f.stat().st_size
                    for f in folder.iterdir()
                    if f.is_file() and f.suffix not in {".json", ".lock"}
                )
                self._budget(size)
                self._print_progress(
                    data.get("downloaded_bytes", 0),
                    data.get("total_bytes") or data.get("total_bytes_estimate"),
                )

            options["progress_hooks"] = [progress]
            if self.options.mode == "audio":
                options["postprocessors"] = [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
                ]
        return options

    def web(self, url: str) -> list[dict]:
        from importlib import import_module

        index = self._index(url, "web")
        with _lock(index.with_suffix(".lock")):
            pointer = _read_cache_json(index)
            if isinstance(pointer.get("manifest"), str):
                with _lock(Path(pointer["manifest"]).with_name(".lock")):
                    if material := self._cached(Path(pointer["manifest"])):
                        return [{"url": url, "status": "cached", "material": material}]
            print(f"解析网页: {url}", flush=True)
            params = self._ydl_options()
            params["extract_flat"] = "in_playlist"
            with import_module("yt_dlp").YoutubeDL(params) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                raise DownloadFailure("NO_MEDIA", "No video metadata was returned")
            if info.get("_type") in {"playlist", "multi_video"}:
                if not self.options.playlist:
                    raise DownloadFailure(
                        "PLAYLIST_REQUIRES_FLAG",
                        "This link is a playlist; pass --playlist and optionally --limit",
                    )
                results = []
                for entry in list(info.get("entries") or [])[: self.options.limit]:
                    if not entry:
                        continue
                    child_url = entry.get("webpage_url") or entry.get("url")
                    if entry.get("_type") in {"url", "url_transparent"}:
                        results.extend(self.acquire(child_url, source="web"))
                    else:
                        results.append(self._web_entry(child_url or url, entry))
                if not results:
                    raise DownloadFailure(
                        "EMPTY_PLAYLIST", "Playlist contains no accessible entries"
                    )
                return results
            result = self._web_entry(url, info)
            if result.get("material"):
                atomic_json(index, {"manifest": result.pop("manifest")})
            return [result]

    def _web_entry(self, url: str, info: dict) -> dict:
        platform = re.sub(
            r"[^A-Za-z0-9_.-]",
            "_",
            info.get("extractor_key") or info.get("extractor") or "generic",
        ).lower()
        media_id = str(info.get("id") or _hash(url))
        identity = media_id
        if platform in {"generic", "html5mediaembed", "html5", "unknown"}:
            identity += "-" + _hash(info.get("webpage_url") or url)
        folder = (
            self.cache
            / "imports"
            / platform
            / _hash([identity, self.options.variant()])
        )
        manifest = folder / "material.json"
        try:
            with _lock(folder / ".lock"):
                self._clear_retained(str(folder))
                if material := self._cached(manifest):
                    return {
                        "url": url,
                        "status": "cached",
                        "material": material,
                        "manifest": str(manifest),
                    }
                import yt_dlp

                with yt_dlp.YoutubeDL(self._ydl_options(folder)) as ydl:
                    downloaded = ydl.process_ie_result(info, download=True)
                candidates = [
                    p
                    for p in folder.glob("source.*")
                    if p.suffix
                    in {
                        ".mp4",
                        ".mkv",
                        ".webm",
                        ".m4a",
                        ".mp3",
                        ".opus",
                        ".ogg",
                        ".wav",
                    }
                    and not re.search(r"\.f[^.]+\.", p.name)
                ]
                if len(candidates) != 1:
                    raise DownloadFailure(
                        "NO_MEDIA",
                        "Download did not produce one complete media file (check size limits and formats)",
                    )
                kind = "music" if self.options.mode == "audio" else "video"
                print(f"校验素材: {info.get('title', media_id)}", flush=True)
                subtitles = []
                for language, track in (
                    downloaded.get("requested_subtitles") or {}
                ).items():
                    path = Path(
                        track.get("filepath")
                        or folder / f"source.{language}.{track['ext']}"
                    )
                    if path.is_file():
                        subtitles.append(
                            {
                                "language": language,
                                "origin": "platform",
                                "generation": "automatic"
                                if language in (info.get("automatic_captions") or {})
                                and language not in (info.get("subtitles") or {})
                                else "unspecified",
                                "path": str(path),
                                "bytes": path.stat().st_size,
                                "sha256": checksum(path),
                            }
                        )
                measured = self._inspect_download(candidates[0], kind)
                if self.options.subtitles and not subtitles:
                    print("平台未返回所选语言的字幕；本次未运行语音识别", flush=True)
                height = {"preview": 360, "edit": 720, "source": None}[
                    self.options.quality
                ]
                if kind == "video" and height:
                    dimensions = next(
                        s for s in measured["streams"] if s["codec_type"] == "video"
                    )
                    if (
                        min(dimensions.get("width", 0), dimensions.get("height", 0))
                        > height
                    ):
                        raise DownloadFailure(
                            "FORMAT_UNAVAILABLE",
                            f"Source has no verified {height}p format; try a higher --quality",
                        )
                material = {
                    "id": f"{platform}-{identity}",
                    "platform": platform,
                    "source_id": media_id,
                    "source": "web",
                    "kind": kind,
                    "url": info.get("webpage_url") or url,
                    "page": info.get("webpage_url") or url,
                    "title": info.get("title"),
                    "credit": info.get("uploader") or "",
                    "license": info.get("license") or "unknown",
                    "tags": info.get("tags") or [],
                    "subtitles": subtitles,
                    "requested": self.options.variant(),
                    **measured,
                }
                self._claim(material)
                atomic_json(manifest, material)
                return {
                    "url": url,
                    "status": "downloaded",
                    "material": material,
                    "manifest": str(manifest),
                }
        except Exception as exc:  # noqa: BLE001 -- isolate vendor failures per batch item
            self._retain(str(folder), folder.glob("source.*"))
            return {
                "url": url,
                "status": "failed",
                "source": "web",
                "error": _error(exc),
            }

    def acquire(
        self,
        url: str,
        *,
        source: str = "auto",
        kind: str = "video",
        preferred: Path | None = None,
        referer: str = "",
    ) -> list[dict]:
        try:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise DownloadFailure(
                    "INVALID_URL", "Expected an http:// or https:// media URL"
                )
            if source == "auto":
                source = (
                    "direct"
                    if Path(parsed.path).suffix.lower() in MEDIA_EXTENSIONS
                    else "web"
                )
            if source == "web":
                active = getattr(self, "active_urls", set())
                if url in active:
                    raise DownloadFailure(
                        "CYCLIC_PLAYLIST", "Playlist links back to an active source"
                    )
                self.active_urls = active
                active.add(url)
                try:
                    return self.web(url)
                finally:
                    active.remove(url)
            if source != "direct":
                raise DownloadFailure("INVALID_SOURCE", f"Unknown source: {source}")
            material, status = self.direct(
                url, kind, preferred=preferred, referer=referer
            )
            return [{"url": url, "status": status, "material": material}]
        except Exception as exc:  # noqa: BLE001 -- report a retryable per-source failure
            return [
                {"url": url, "source": source, "status": "failed", "error": _error(exc)}
            ]


def download_urls(
    urls: list[str],
    cache: Path,
    options: DownloadOptions | None = None,
    *,
    output: Path | None = None,
) -> dict:
    options = options or DownloadOptions()
    importer = Importer(cache, options)
    results = []
    for index, url in enumerate(urls):
        try:
            results.extend(importer.acquire(url))
        except KeyboardInterrupt:
            for pending_index, pending in enumerate(urls[index:]):
                results.append(
                    {
                        "url": pending,
                        "status": "failed",
                        "error": {
                            "code": "NOT_ATTEMPTED" if pending_index else "INTERRUPTED",
                            "message": "Interrupted; rerun or retry this report to finish pending sources",
                        },
                    }
                )
            if output:
                save_report(make_report(results, cache, options), output)
            raise
        if output:
            save_report(make_report(results, cache, options), output)
    report = make_report(results, cache, options)
    if output:
        save_report(report, output)
    return report


def save_report(report: dict, output: Path):
    atomic_json(output / "materials.json", report["materials"])
    atomic_json(output / "download-report.json", report)


def make_report(results: list[dict], cache: Path, options: DownloadOptions) -> dict:
    return {
        "schema": "videocut-download-v1",
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "cache": str(cache.resolve()),
        "options": options.public(),
        "results": results,
        "failed": sum(r["status"] == "failed" for r in results),
        "materials": [r["material"] for r in results if r.get("material")],
    }

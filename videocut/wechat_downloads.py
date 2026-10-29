"""Optional wx_channels_download v260907 local API adapter.

The external service owns capture/decryption. This adapter never installs a
certificate, changes a proxy, reads cookies, or chooses an unrelated recent feed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .downloads import DownloadFailure, _hash, _lock, _read_cache_json, atomic_json
from .media import run


def validate_api_url(url: str) -> None:
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
        valid = (
            parts.scheme == "http"
            and parts.hostname in {"127.0.0.1", "localhost", "::1"}
            and not parts.username
            and not parts.password
            and parts.path in {"", "/"}
            and not parts.query
            and not parts.fragment
            and port != 0
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError(
            "--wechat-api must be a loopback HTTP origin, e.g. http://127.0.0.1:2022"
        )


def is_wechat_url(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    return (
        p.hostname == "weixin.qq.com"
        and p.path.startswith("/sph/")
        or p.hostname == "channels.weixin.qq.com"
        and p.path
        in {
            "/web/pages/feed",
            "/finder-preview/pages/feed",
            "/finder-preview/pages/sph",
        }
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DownloadFailure(
            "WECHAT_API_ERROR", "Local WeChat API unexpectedly redirected"
        )


class WeChatClient:
    def __init__(self, origin: str):
        validate_api_url(origin)
        self.origin = origin.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def request(self, path: str, *, query=None, body=None) -> dict:
        url = self.origin + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(req, timeout=20) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError("oversized response")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("code") != 0:
                raise ValueError("API failure")
            result = data["data"]
            if not isinstance(result, dict):
                raise TypeError("invalid data")
            return result
        except DownloadFailure:
            raise
        except urllib.error.HTTPError as exc:
            raise DownloadFailure(
                "WECHAT_API_ERROR",
                f"Local WeChat API returned HTTP {exc.code}; check its version and session",
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DownloadFailure(
                "WECHAT_SERVICE_UNAVAILABLE",
                "Start wx_channels_download (tested v260907) locally; check --wechat-api. "
                "Certificate/proxy setup is managed separately; videocut does not change it.",
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            # Vendor error bodies may contain signed URLs or credentials.
            raise DownloadFailure(
                "WECHAT_API_ERROR", "Invalid or failed response from local WeChat API"
            ) from exc

    def captures(self, limit: int = 20) -> list[dict]:
        records = []
        for page in range(1, (limit + 49) // 50 + 1):
            data = self.request(
                "/api/browse_history/list",
                body={
                    "platform_id": "wxchannels",
                    "page": page,
                    "page_size": min(limit, 50),
                },
            )
            rows = data.get("list") or []
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) for row in rows
            ):
                raise DownloadFailure(
                    "WECHAT_API_ERROR", "Invalid capture list from local WeChat API"
                )
            records.extend(
                row for row in rows if row.get("platform_id") == "wxchannels"
            )
            if not rows or page * min(limit, 50) >= data.get("total", 0):
                break
        return records[:limit]

    def profile(self, url: str, feed_id: str | None) -> dict:
        if not self.request("/api/channels/status").get("available"):
            raise DownloadFailure(
                "WECHAT_PAGE_REQUIRED",
                "Reopen the target video in WeChat, play it, then retry",
            )
        parts = urllib.parse.urlsplit(url)
        params = (
            urllib.parse.parse_qs(parts.query)
            if parts.hostname == "channels.weixin.qq.com"
            and parts.path.endswith("/feed")
            else {}
        )
        selector = {
            key: params[key][0] for key in ("oid", "nid", "eid") if params.get(key)
        }
        if feed_id or not (
            selector.get("eid") or selector.get("oid") and selector.get("nid")
        ):
            matches = [
                row
                for row in self.captures(1000)
                if (
                    str(row.get("external_id")) == feed_id
                    if feed_id
                    else url in {row.get("url"), row.get("source_url")}
                )
            ]
            if len(matches) != 1:
                raise DownloadFailure(
                    "WECHAT_CAPTURE_REQUIRED",
                    "Cannot uniquely match this link to a captured video. Play the target in WeChat; "
                    "run 'videocut download --wechat-list', then pass its --wechat-feed-id. "
                    "The most recent video is never selected implicitly.",
                )
            extra = matches[0].get("extra_data") or {}
            try:
                if isinstance(extra, str):
                    extra = json.loads(extra)
                selector = {
                    "oid": str(extra.get("id") or matches[0]["external_id"]),
                    "nid": extra["nonce_id"],
                }
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise DownloadFailure(
                    "WECHAT_CAPTURE_REQUIRED",
                    "Capture has no video nonce; reopen the target in WeChat",
                ) from exc
        data = self.request("/api/channels/feed/profile", query=selector)
        try:
            if data.get("errCode") != 0:
                raise ValueError("platform failure")
            obj = data["data"]["object"]
            if not isinstance(obj, dict) or not obj.get("id"):
                raise ValueError("missing object")
            # Web links can carry an opaque oid rather than the numeric object ID.
            expected = feed_id or (
                selector.get("oid")
                if str(selector.get("oid", "")).isdecimal()
                else None
            )
            if expected and str(obj["id"]) != expected:
                raise ValueError("mismatched video ID")
            return obj
        except (ValueError, KeyError, TypeError) as exc:
            raise DownloadFailure(
                "WECHAT_PROFILE_ERROR",
                "WeChat returned missing or mismatched video details",
            ) from exc


def select_spec(media: dict, quality: str) -> dict:
    cap = {"preview": 360, "edit": 720, "source": float("inf")}[quality]
    specs = [
        s
        for s in media.get("spec", [])
        if (
            isinstance(s, dict)
            and s.get("fileFormat")
            and isinstance(s.get("width"), (int, float))
            and isinstance(s.get("height"), (int, float))
            and 0 < min(s["width"], s["height"]) <= cap
        )
    ]
    if not specs:
        raise DownloadFailure(
            "FORMAT_UNAVAILABLE",
            "No explicit WeChat format matches --quality; try edit or source",
        )
    # Prefer actual advertised formats over the unreliable synthetic 'original'.
    return max(
        specs,
        key=lambda s: (
            min(s["width"], s["height"]),
            s.get("codingFormat") == "h264",
            s.get("videoBitrate", s.get("bitRate", 0)),
        ),
    )


def import_wechat(importer, url: str) -> list[dict]:
    if not is_wechat_url(url):
        raise DownloadFailure(
            "INVALID_URL", "Expected a WeChat Channels share or feed URL"
        )
    options = importer.options
    index = importer._index(url, "wechat")
    with _lock(index.with_suffix(".lock")):
        pointer = _read_cache_json(index)
        manifest_path = pointer.get("manifest")
        if isinstance(manifest_path, str):
            with _lock(Path(manifest_path).with_name(".lock")):
                if material := importer._cached(Path(manifest_path)):
                    return [
                        {
                            "url": url,
                            "source": "wechat",
                            "status": "cached",
                            "material": material,
                        }
                    ]
        client = WeChatClient(options.wechat_api)
        obj = client.profile(url, options.wechat_feed_id)
        try:
            media = obj["objectDesc"]["media"][0]
            if obj.get("liveInfo") or media.get("mediaType") not in {4, None}:
                raise ValueError("not a video")
            spec = select_spec(media, options.quality)
            remote = str(media["url"]) + str(media.get("urlToken", ""))
            parsed = urllib.parse.urlsplit(remote)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "finder.video.qq.com"
                or parsed.username
                or parsed.password
            ):
                raise ValueError("unexpected media origin")
            key = str(media["decodeKey"])
            if not key.isdecimal() or not 0 <= int(key) < 2**64:
                raise ValueError("invalid decryption key")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DownloadFailure(
                "WECHAT_PROFILE_ERROR",
                "WeChat profile has no usable video/decryption metadata",
            ) from exc
        # Preserve the original encoding of signed CDN query parameters.
        query = [
            part
            for part in parsed.query.split("&")
            if (
                part
                and urllib.parse.unquote(part.split("=", 1)[0]).lower()
                != "x-snsvideoflag"
            )
        ]
        query.append(
            "X-snsvideoflag=" + urllib.parse.quote(spec["fileFormat"], safe="")
        )
        remote = urllib.parse.urlunsplit(parsed._replace(query="&".join(query)))
        stream = (
            client.origin
            + "/play?"
            + urllib.parse.urlencode({"url": remote, "key": key})
        )
        folder = (
            importer.cache
            / "imports/wechat"
            / _hash([str(obj["id"]), options.variant()])
        )
        manifest = folder / "material.json"
        with _lock(folder / ".lock"):
            if material := importer._cached(manifest):
                atomic_json(index, {"manifest": str(manifest)})
                return [
                    {
                        "url": url,
                        "source": "wechat",
                        "status": "cached",
                        "material": material,
                    }
                ]
            target = folder / "source.mp4"
            try:
                print(f"下载微信视频号: {obj['id']} · {spec['fileFormat']}", flush=True)
                importer._http(stream, target, local=True)
            except DownloadFailure:
                raise
            except Exception as exc:
                raise DownloadFailure(
                    "WECHAT_TRANSFER_FAILED",
                    "Local WeChat decrypted stream failed; reopen the video and retry",
                ) from exc
            finally:
                # Do not retain signed CDN URLs/decryption keys in resume metadata.
                target.with_name(target.name + ".part.json").unlink(missing_ok=True)
            measured = importer._inspect_download(target, "video")
            video = next(s for s in measured["streams"] if s["codec_type"] == "video")
            if (video.get("width"), video.get("height")) != (
                int(spec["width"]),
                int(spec["height"]),
            ):
                target.unlink(missing_ok=True)
                raise DownloadFailure(
                    "FORMAT_UNAVAILABLE",
                    "WeChat returned a different resolution from the selected format; reopen and retry",
                )
            if options.mode == "audio":
                track = next(
                    (s for s in measured["streams"] if s["codec_type"] == "audio"), None
                )
                if not track:
                    raise DownloadFailure(
                        "NO_AUDIO", "WeChat video has no audio stream"
                    )
                audio = folder / "audio.m4a"
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
                        "copy" if track.get("codec_name") == "aac" else "aac",
                        str(audio),
                    ]
                )
                measured = importer._inspect_download(audio, "music")
                target.unlink(missing_ok=True)
            if options.subtitles:
                print("视频号未提供独立字幕轨；未运行语音识别", flush=True)
            material = {
                "id": "wechat-" + str(obj["id"]),
                "platform": "wechat",
                "source_id": str(obj["id"]),
                "source": "wechat",
                "kind": "music" if options.mode == "audio" else "video",
                "url": url,
                "page": url,
                "title": obj["objectDesc"].get("description", ""),
                "credit": obj.get("nickname")
                or (obj.get("contact") or {}).get("nickname", ""),
                "license": "unknown",
                "tags": [],
                "subtitles": [],
                "wechat_spec": spec["fileFormat"],
                "backend": "wx_channels_download",
                "requested": options.variant(),
                **measured,
            }
            importer._claim(material)
            atomic_json(manifest, material)
            atomic_json(index, {"manifest": str(manifest)})
            return [
                {
                    "url": url,
                    "source": "wechat",
                    "status": "downloaded",
                    "material": material,
                }
            ]

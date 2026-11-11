"""Read-only Channels account/comment collection through the local bridge.

No cookies, system proxy changes, certificate installation, or video selection
by recency. Successful pages can resume; incomplete pagination is never success.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .downloads import DownloadFailure, _lock, atomic_json
from .wechat_downloads import WeChatClient

SCHEMA = 1


def save_private(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_json(path, value)
    path.chmod(0o600)


def api_data(client: WeChatClient, endpoint: str, params: dict) -> dict:
    """Check both the bridge envelope and the WeChat envelope, without echoing secrets."""
    result = client.request("/api/channels/" + endpoint, query=params)
    if result.get("errCode") != 0 or not isinstance(result.get("data"), dict):
        raise DownloadFailure(
            "WECHAT_BRIDGE_ERROR",
            "WeChat API bridge failed; refresh the page and check compatibility. "
            "See docs/wechat-channels.md (finderSearch / script errors).",
        )
    data = result["data"]
    base = data.get("BaseResponse", {})
    if not isinstance(base, dict) or base.get("Ret", 0) != 0:
        raise DownloadFailure("WECHAT_BRIDGE_ERROR", "WeChat rejected the request")
    return data


def rows(data: dict, field: str) -> list[dict]:
    result = data.get(field)
    if not isinstance(result, list) or any(not isinstance(x, dict) for x in result):
        raise ValueError("Invalid or missing " + field)
    return result


def flag(data: dict, field: str) -> bool:
    value = data.get(field)
    if type(value) not in (int, bool) or value not in (0, 1):
        raise ValueError("Missing/invalid pagination flag: " + field)
    return bool(value)


def identifier(value) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value):
        raise ValueError("Missing identifier")
    return str(value)


def clean_comment(c: dict) -> dict:
    region = c.get("ipRegionInfo") or {}
    return {
        "id": identifier(c.get("commentId")),
        "user": c.get("username"),
        "nickname": c.get("nickname", ""),
        "text": c.get("content", ""),
        "likes": c.get("likeCount", 0),
        "time": c.get("createtime"),
        "region": region.get("regionText"),
        "reply_to": c.get("replyCommentId"),
        "more_replies": bool(c.get("continueFlag")),
        "reply_count": c.get("expandCommentCount", 0),
        "preview": [clean_comment(r) for r in c.get("levelTwoComment", [])],
    }


def clean_page(endpoint: str, data: dict) -> dict:
    if endpoint == "contact/feed/list":
        items = []
        for v in rows(data, "object"):
            items.append(
                {
                    "id": identifier(v.get("id")),
                    "nonce": identifier(v.get("objectNonceId")),
                    "title": (v.get("objectDesc") or {}).get("description", ""),
                    "published": v.get("createtime"),
                    "likes": v.get("likeCount"),
                    "forwards": v.get("forwardCount"),
                    "favorites": v.get("favCount"),
                    "display_comment_count": v.get("commentCount"),
                }
            )
        more = flag(data, "continueFlag")
    else:
        items = [clean_comment(c) for c in rows(data, "commentInfo")]
        more = flag(data, "downContinueFlag")
    marker = data.get("lastBuffer") or ""
    if not isinstance(marker, str):
        raise TypeError("Invalid page cursor")
    return {"items": items, "more": more, "cursor": marker}


def search(client: WeChatClient, keyword: str, marker: str = "") -> dict:
    data = api_data(
        client, "contact/search", {"keyword": keyword, "next_marker": marker}
    )
    accounts = []
    for row in rows(data, "infoList"):
        c = row.get("contact") or {}
        if c.get("username"):
            accounts.append(
                {"username": c["username"], "nickname": c.get("nickname", "")}
            )
    return {
        "accounts": accounts,
        "more": flag(data, "continueFlag"),
        "next_marker": data.get("lastBuff") or "",
    }


class Collector:
    def __init__(
        self, client: WeChatClient, output: Path, *, max_pages=1000, delay=0.15
    ):
        if max_pages < 1 or delay < 0:
            raise ValueError("max_pages must be positive and delay nonnegative")
        self.client, self.output = client, output
        self.max_pages, self.delay = max_pages, delay
        self.requests = self.cached = 0

    def page(self, endpoint: str, params: dict) -> dict:
        identity = json.dumps(
            [SCHEMA, self.client.origin, endpoint, params], sort_keys=True
        )
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.output / "pages" / (key + ".json")
        if path.exists():
            try:
                cached = json.loads(path.read_text())
                if cached["identity_hash"] == key and cached["schema"] == SCHEMA:
                    p = cached["page"]
                    digest = hashlib.sha256(
                        json.dumps(p, sort_keys=True).encode()
                    ).hexdigest()
                    if cached.get("payload_sha256") != digest:
                        raise ValueError("Damaged page cache")
                    if (
                        isinstance(p["items"], list)
                        and type(p["more"]) is bool
                        and isinstance(p["cursor"], str)
                    ):
                        self.cached += 1
                        return p
            except (ValueError, KeyError, TypeError):
                pass  # damaged page: refetch, do not silently count it as complete
        for attempt in range(3):
            try:
                time.sleep(self.delay)
                self.requests += 1
                result = clean_page(endpoint, api_data(self.client, endpoint, params))
                save_private(
                    path,
                    {
                        "schema": SCHEMA,
                        "identity_hash": key,
                        "page": result,
                        "payload_sha256": hashlib.sha256(
                            json.dumps(result, sort_keys=True).encode()
                        ).hexdigest(),
                        "captured_at": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                        ),
                    },
                )
                return result
            except DownloadFailure:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise AssertionError("unreachable")

    def walk(self, endpoint: str, params: dict, accept) -> tuple[bool, str | None]:
        marker, seen = "", set()
        try:
            for _ in range(self.max_pages):
                p = self.page(endpoint, {**params, "next_marker": marker})
                for item in p["items"]:
                    accept(item)
                if not p["more"]:
                    return True, None
                nxt = p["cursor"]
                if not nxt or nxt == marker or nxt in seen:
                    return False, "PAGINATION_STALLED"
                seen.add(nxt)
                marker = nxt
            return False, "PAGE_LIMIT_REACHED"
        except DownloadFailure as exc:
            return False, exc.code
        except (ValueError, TypeError, KeyError):
            return False, "INVALID_PAGE_DATA"

    def collect(self, username: str) -> dict:
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _lock(self.output / ".collection.lock"):
            return self._collect(username)

    def _collect(self, username: str) -> dict:
        if not username.strip():
            raise ValueError("Explicit account username is required")
        metadata = self.output / "request.json"
        request = {"schema": SCHEMA, "api": self.client.origin, "username": username}
        if metadata.exists() and json.loads(metadata.read_text()) != request:
            raise ValueError(
                "Output belongs to a different account/API; use a new directory"
            )
        save_private(metadata, request)
        videos = {}
        complete, error = self.walk(
            "contact/feed/list",
            {"username": username},
            lambda v: videos.__setitem__(v["id"], v),
        )
        results = []
        report = {
            "schema": SCHEMA,
            "username": username,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "feed_list_complete": complete,
            "errors": [error] if error else [],
            "complete": False,
            "videos": results,
        }
        save_private(self.output / "collection.json", report)
        for v in videos.values():
            found, roots = {}, {}

            def add(c, parent=None, *, found=found):
                clean = {
                    k: val
                    for k, val in c.items()
                    if k not in {"preview", "more_replies", "reply_count"}
                }
                clean.update(parent_id=parent, is_author=c["user"] == username)
                found[c["id"]] = clean
                for reply in c["preview"]:
                    add(reply, c["id"])

            def root(c, *, roots=roots, add=add):
                roots[c["id"]] = c
                add(c)

            root_ok, root_err = self.walk(
                "feed/comment/list", {"oid": v["id"], "nid": v["nonce"]}, root
            )
            reply_ok, errors = True, [root_err] if root_err else []
            for cid, c in roots.items():
                if not c["more_replies"] and c["reply_count"] <= len(c["preview"]):
                    continue
                ok, err = self.walk(
                    "feed/comment/list",
                    {"oid": v["id"], "comment_id": cid},
                    lambda r, cid=cid: add(r, cid),
                )
                if not ok:
                    reply_ok = False
                    errors.append(f"{cid}: {err}")
            result = {k: val for k, val in v.items() if k != "nonce"}
            result.update(
                root_complete=root_ok,
                replies_complete=reply_ok,
                errors=errors,
                root_count=len(roots),
                collected_count=len(found),
                comments=list(found.values()),
            )
            results.append(result)
            save_private(self.output / "collection.json", report)
        report.update(
            complete=complete
            and all(v["root_complete"] and v["replies_complete"] for v in results),
            requests=self.requests,
            cached_pages=self.cached,
            video_count=len(results),
            comment_count=sum(v["collected_count"] for v in results),
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        save_private(self.output / "collection.json", report)
        return report

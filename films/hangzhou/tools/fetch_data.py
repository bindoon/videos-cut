"""Fetch CMAB city files by ZIP ranges, and the actual OSM water/road geometry.

The source ZIP remains remote. Its per-city shapefile headers identify the city
spatially; no guess based on an opaque city ID or filename is accepted.
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import pathlib
import struct
import urllib.parse
import urllib.request
import zipfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
CACHE = ROOT / "assets/cache/hangzhou"
META = CACHE / "cmab-metadata.json"
BBOX = [120.055, 30.155, 120.285, 30.365]


def request(url, start=None, end=None, data=None, timeout=120):
    headers = {"User-Agent": "HangzhouRings/1.0 (local educational film)"}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
    req = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if start is not None:
            cr = r.headers.get("Content-Range", "")
            if r.status != 206 or not cr.startswith(f"bytes {start}-"):
                raise ValueError(f"Server did not honor range {start}-{end}: {r.status} {cr}")
        return r.read()


def cmab():
    CACHE.mkdir(parents=True, exist_ok=True)
    if META.exists():
        meta = json.loads(META.read_text())
    else:
        meta = json.loads(request("https://api.figshare.com/v2/articles/27992417/versions/2"))
    (CACHE / "cmab-metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    f = next(x for x in meta["files"] if x["name"] == "zhejiang.zip")
    url, size = f["download_url"], f["size"]
    tail_path = CACHE / "zhejiang-central-directory.bin"
    if not tail_path.exists():
        tail_path.write_bytes(request(url, size - 131072, size - 1))
    tail = tail_path.read_bytes()
    z = zipfile.ZipFile(io.BytesIO(tail))
    base = size - len(tail)
    infos = z.infolist()

    def entry(info, prefix=False):
        off = base + info.header_offset
        # A range per member includes its local header and compressed data.
        count = min(info.compress_size, 32768) if prefix else info.compress_size
        raw = request(url, off, off + 30 + len(info.filename.encode("utf-8")) + 1024 + count)
        sig, _, flags, method, _, _, crc, cs, fs, nl, el = struct.unpack_from("<4s5H3L2H", raw)
        if sig != b"PK\x03\x04":
            raise ValueError(f"Missing ZIP local header: {info.filename} at {off}")
        compressed = raw[30 + nl + el:30 + nl + el + info.compress_size]
        if method == 0:
            data = compressed
        elif method == 8:
            data = zlib.decompressobj(-15).decompress(compressed)
        else:
            raise ValueError(f"Unsupported ZIP method {method}")
        if not prefix and (len(data) != info.file_size or zlib.crc32(data) != info.CRC):
            raise ValueError(f"CRC or size mismatch: {info.filename}")
        return data

    # The regional megacity is among the largest natural-city files. Verify
    # geometry rather than treating its opaque numeric ID as a city name.
    candidates = sorted((i for i in infos if i.filename.endswith(".shp")), key=lambda i: -i.file_size)[:20]
    inspection_path = CACHE / "city-inspection.json"
    if inspection_path.exists():
        inspection = json.loads(inspection_path.read_text())
    else:
        from pyproj import CRS, Transformer

        def inspect(i):
            h = entry(i, True)
            bbox = struct.unpack_from("<4d", h, 36)
            prj = next(j for j in infos if j.filename == i.filename[:-4] + ".prj")
            crs = CRS.from_wkt(entry(prj).decode())
            tx = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
            a, b = tx.transform(bbox[0], bbox[1]), tx.transform(bbox[2], bbox[3])
            result = {"name": i.filename, "bbox": [*a, *b], "size": i.file_size, "crs": crs.to_string()}
            print("CITY", result, flush=True)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            inspection = list(ex.map(inspect, candidates))
        inspection_path.write_text(json.dumps(inspection, ensure_ascii=False, indent=2))
    selected = [i for i in inspection if i["bbox"][0] < 120.17 < i["bbox"][2] and i["bbox"][1] < 30.25 < i["bbox"][3]]
    if len(selected) != 1:
        raise ValueError(f"Expected one Hangzhou natural-city extent, found {selected}")
    stem = selected[0]["name"][:-4]
    city = CACHE / "cmab-city"
    city.mkdir(exist_ok=True)
    for i in infos:
        if i.filename.startswith(stem + "."):
            dest = city / pathlib.Path(i.filename).name
            if not dest.exists():
                print("FETCH", i.filename, i.compress_size, flush=True)
                data = entry(i)
                dest.write_bytes(data)
    (CACHE / "cmab-selection.json").write_text(json.dumps(selected[0], ensure_ascii=False, indent=2))


def osm():
    dest = CACHE / "osm.json"
    if dest.exists():
        return
    s, w, n, e = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
    bb = f"({s},{w},{n},{e})"
    query = f'''[out:json][timeout:180];(
way["natural"="water"]{bb};relation["natural"="water"]{bb};
way["waterway"~"river|canal"]{bb};
way["highway"~"motorway|trunk|primary"]{bb};
);out geom;'''
    body = urllib.parse.urlencode({"data": query}).encode()
    for endpoint in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
        try:
            data = request(endpoint, data=body, timeout=240)
            parsed = json.loads(data)
            if "remark" in parsed:
                raise ValueError(parsed["remark"])
            dest.write_bytes(data)
            print("OSM", len(parsed["elements"]), len(data), flush=True)
            break
        except Exception as exc:
            print("OSM endpoint failed", endpoint, repr(exc), flush=True)
    else:
        raise RuntimeError("Unable to download OSM water geometry")


def osm_direct():
    """OSM main API fallback, identified from an actual map response.

    Relation 8227206 is the Qiantang water multipolygon returned by the map
    API at 120.20,30.23–120.22,30.25, not an assumed river centreline buffer.
    """
    requests = [
        ("river-full", "https://api.openstreetmap.org/api/0.6/relation/8227206/full.json"),
        ("canal-map", "https://api.openstreetmap.org/api/0.6/map.json?bbox=120.13,30.30,120.16,30.33"),
        ("sudi-map", "https://api.openstreetmap.org/api/0.6/map.json?bbox=120.125,30.228,120.14,30.263"),
    ]
    def get(item):
        name, url = item
        dest = CACHE / f"osm-{name}.json"
        if not dest.exists():
            dest.write_bytes(request(url, timeout=120))
        d = json.loads(dest.read_text())
        print("OSM main API", name, len(d["elements"]), flush=True)
        return d["elements"]
    all_elements = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for elements in ex.map(get, requests):
            for e in elements:
                all_elements[(e["type"], e["id"])] = e
    existing = CACHE / "osm-map-river.json"
    if existing.exists():
        for e in json.loads(existing.read_text())["elements"]:
            all_elements[(e["type"], e["id"])] = e
    nodes = {i: e for (kind, i), e in all_elements.items() if kind == "node"}
    ways = {i: e for (kind, i), e in all_elements.items() if kind == "way"}
    result = []
    for (_, _), e in all_elements.items():
        tags = e.get("tags", {})
        if e["type"] == "way" and (tags.get("natural") == "water" or tags.get("waterway") or tags.get("highway")):
            if all(n in nodes for n in e["nodes"]):
                result.append({**e, "geometry": [{"lon": nodes[n]["lon"], "lat": nodes[n]["lat"]} for n in e["nodes"]]})
        if e["type"] == "relation" and tags.get("natural") == "water":
            members = []
            complete = True
            for m in e.get("members", []):
                if m["type"] != "way":
                    continue
                w = ways.get(m["ref"])
                if not w or not all(n in nodes for n in w["nodes"]):
                    complete = False
                    break
                members.append({**m, "geometry": [{"lon": nodes[n]["lon"], "lat": nodes[n]["lat"]} for n in w["nodes"]]})
            if complete:
                result.append({**e, "members": members})
    (CACHE / "osm.json").write_text(json.dumps({"source": "OpenStreetMap main API", "elements": result}, ensure_ascii=False))
    print("OSM GEOMETRY", len(result), flush=True)


if __name__ == "__main__":
    import sys
    if "--osm-direct" in sys.argv:
        osm_direct()
    elif "--osm" in sys.argv:
        osm()
    else:
        cmab()

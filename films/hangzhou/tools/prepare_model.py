"""Project and crop real Hangzhou building/water data into a 1:10000 model."""
from __future__ import annotations

from paths import output_directory

import hashlib
import json
import math
import pathlib
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import box, shape, Polygon, LineString, mapping
from shapely.ops import transform, polygonize, unary_union
from shapely import make_valid
from shapely.strtree import STRtree

ROOT = pathlib.Path(__file__).resolve().parents[3]
CACHE = ROOT / "assets/cache/hangzhou"
DATA = ROOT / "films/hangzhou/data"
OUT = None
BBOX = [120.055, 30.155, 120.285, 30.365]
SCALE = 10000
LOCAL = CRS.from_proj4("+proj=aeqd +lat_0=30.26 +lon_0=120.17 +datum=WGS84 +units=m")
GPS = Transformer.from_crs(4326, LOCAL, always_xy=True)
PROJ = Transformer.from_crs(3857, LOCAL, always_xy=True)


def polygons(g):
    if g.geom_type == "Polygon":
        yield g
    elif hasattr(g, "geoms"):
        for p in g.geoms:
            yield from polygons(p)


def rings(g):
    return [[[round(x / SCALE, 6), round(-y / SCALE, 6)] for x, y in list(r.coords)[:-1]]
            for r in [g.exterior, *g.interiors]]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    corners = [GPS.transform(x, y) for x in [BBOX[0], BBOX[2]] for y in [BBOX[1], BBOX[3]]]
    xs, ys = zip(*corners)
    extent = box(min(xs), min(ys), max(xs), max(ys))
    # A small set of explicit OSM heights replaces the coarser CMAB massing
    # where both sources overlap. Never infer landmark height from a picture.
    osm_buildings = {}
    for file in CACHE.glob("osm-*map*.json"):
        raw = json.loads(file.read_text()).get("elements", [])
        nodes = {e["id"]: e for e in raw if e["type"] == "node"}
        for e in raw:
            tags = e.get("tags", {})
            if e["type"] != "way" or not tags.get("building") or not tags.get("height"):
                continue
            try:
                height = float(tags["height"].replace(" m", ""))
            except ValueError:
                continue
            ns = e.get("nodes", [])
            if height < 40 or height > 1000 or len(ns) < 4 or ns[0] != ns[-1] or not all(n in nodes for n in ns):
                continue
            geom = transform(GPS.transform, make_valid(Polygon([(nodes[n]["lon"], nodes[n]["lat"]) for n in ns])))
            if extent.covers(geom):
                for poly in polygons(geom):
                    if poly.area > 9:
                        osm_buildings[e["id"]] = (poly, height, tags.get("name", ""))
    osm_parts = list(osm_buildings.values())
    tree = STRtree([p for p, _, _ in osm_parts]) if osm_parts else None
    tx = Transformer.from_crs(4326, 3857, always_xy=True)
    a, b = tx.transform(BBOX[0], BBOX[1]), tx.transform(BBOX[2], BBOX[3])
    shp = next((CACHE / "cmab-city").glob("*.shp"))
    reader = shapefile.Reader(str(shp), encoding="utf-8", encodingErrors="replace")
    features, invalid, outside, replaced = [], 0, 0, 0
    for sr in reader.iterShapeRecords(fields=["Height", "Age"]):
        s, record = sr.shape, sr.record
        if not hasattr(s, "bbox") or not s.points:
            invalid += 1
            continue
        x0, y0, x1, y1 = s.bbox
        if x1 < a[0] or x0 > b[0] or y1 < a[1] or y0 > b[1]:
            outside += 1
            continue
        try:
            h = float(record["Height"])
        except (ValueError, TypeError):
            invalid += 1
            continue
        if not math.isfinite(h) or h <= 0 or h > 1000:
            invalid += 1
            continue
        geom = transform(PROJ.transform, shape(s.__geo_interface__))
        if not geom.is_valid:
            geom = make_valid(geom)
        if not extent.covers(geom):
            outside += 1
            continue
        for poly in polygons(geom):
            if poly.area < 9:
                invalid += 1
                continue
            poly = poly.simplify(0.55, preserve_topology=True)
            c = poly.centroid
            if tree is not None and any(osm_parts[int(i)][0].covers(c) for i in tree.query(c)):
                replaced += 1
                continue
            features.append([round(h, 2), round(c.x / SCALE, 6), round(-c.y / SCALE, 6), round(poly.area, 2), record["Age"], rings(poly)])
    cmab_max = max(f[0] for f in features)
    for poly, h, _ in osm_parts:
        c = poly.centroid
        features.append([round(h, 2), round(c.x / SCALE, 6), round(-c.y / SCALE, 6), round(poly.area, 2), "OSM height", rings(poly)])
    print("BUILDINGS", len(features), "of", reader.numRecords, flush=True)

    water_features = []
    routes = []
    # Exact downloaded West Lake polygons are also a reliable independently
    # named anchor if an Overpass response has no name on its polygon pieces.
    wp = CACHE / "westlake-nominatim.json"
    if wp.exists():
        for f in json.loads(wp.read_text())["features"]:
            water_features.append(("西湖", "lake", shape(f["geometry"])))
    for file in [CACHE / "osm.json", CACHE / "qiantang-overpass.json"]:
        if not file.exists():
            continue
        osm = json.loads(file.read_text())
        for e in osm.get("elements", []):
            tags = e.get("tags", {})
            name = tags.get("name", "")
            if e["type"] == "relation":
                outers, inners = [], []
                for m in e.get("members", []):
                    points = [(p["lon"], p["lat"]) for p in m.get("geometry", []) if "lon" in p]
                    if len(points) > 1:
                        (inners if m.get("role") == "inner" else outers).append(LineString(points))
                o = unary_union(list(polygonize(unary_union(outers)))) if outers else Polygon()
                holes = unary_union(list(polygonize(unary_union(inners)))) if inners else Polygon()
                geom = o.difference(holes)
                if not geom.is_empty:
                    water_features.append((name, tags.get("water", "water"), geom))
            elif e["type"] == "way":
                points = [(p["lon"], p["lat"]) for p in e.get("geometry", [])]
                if len(points) < 2:
                    continue
                if tags.get("natural") == "water" and points[0] == points[-1] and len(points) > 3:
                    water_features.append((name, tags.get("water", "water"), make_valid(Polygon(points))))
                elif tags.get("waterway") or tags.get("highway"):
                    routes.append((name, tags.get("waterway") or tags.get("highway"), LineString(points), tags.get("bridge", "no")))
    # Main API / Nominatim fallbacks retain the exact OSM geometry and metadata.
    for key, kind in [("qiantang", "river"), ("canal", "canal"), ("sudi", "causeway")]:
        path = CACHE / f"{key}-nominatim.json"
        if path.exists():
            for f in json.loads(path.read_text())["features"]:
                g = shape(f["geometry"])
                name = f["properties"].get("name", key)
                if g.geom_type in ["Polygon", "MultiPolygon"]:
                    water_features.append((name, kind, g))
                elif "LineString" in g.geom_type:
                    for line in ([g] if g.geom_type == "LineString" else g.geoms):
                        routes.append((name, kind, line, "no"))

    water, lines = [], []
    for name, kind, g in water_features:
        g = transform(GPS.transform, g).intersection(extent)
        for poly in polygons(g):
            if poly.area > 150:
                poly = poly.simplify(2, preserve_topology=True)
                water.append({"name": name, "kind": kind, "rings": rings(poly)})
    for name, kind, g, bridge in routes:
        g = transform(GPS.transform, g).intersection(extent)
        parts = [g] if g.geom_type == "LineString" else list(getattr(g, "geoms", []))
        for line in parts:
            if line.geom_type == "LineString" and line.length > 80:
                line = line.simplify(3)
                lines.append({"name": name, "kind": kind, "bridge": bridge, "points": [[round(x / SCALE, 6), round(-y / SCALE, 6)] for x, y in line.coords]})
    if not any(w["name"] == "西湖" for w in water):
        raise ValueError("West Lake geometry is missing")
    if not any(w["kind"] == "river" for w in water):
        raise ValueError("Qiantang River water polygons missing; do not replace with an invented river")
    anchors_gps = {
        "westlake": [120.1390, 30.2450], "sudi": [120.1292, 30.2440],
        "oldcity": [120.1700, 30.2495], "palace": [120.1676, 30.2189],
        "canal": [120.1417, 30.3158], "qianjiang": [120.2110, 30.2500],
        "binjiang": [120.2080, 30.2080], "olympic": [120.2284, 30.2295],
        "river": [120.2130, 30.2350], "wulin": [120.1580, 30.2740]
    }
    anchors = {k: [round(GPS.transform(*v)[0] / SCALE, 6), round(-GPS.transform(*v)[1] / SCALE, 6)] for k, v in anchors_gps.items()}
    causeways = [LineString(r["points"]) for r in lines if "苏堤" in r["name"] or r["kind"] == "causeway"]
    if causeways:
        from shapely.ops import linemerge
        network = linemerge(unary_union(causeways))
        candidates = [network] if network.geom_type == "LineString" else list(network.geoms)
        midpoint = max(candidates, key=lambda g: g.length).interpolate(.5, normalized=True)
        anchors["sudi"] = [round(midpoint.x, 6), round(midpoint.y, 6)]
    model = {"scale": SCALE, "bbox_wgs84": BBOX, "crs": LOCAL.to_string(), "size": [(max(xs) - min(xs)) / SCALE, (max(ys) - min(ys)) / SCALE], "buildings": features, "water": water, "routes": lines, "anchors": anchors}
    (DATA / "model.json").write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")))
    stats = {"source_records": reader.numRecords, "building_parts": len(features), "excluded_outside": outside, "excluded_invalid_or_tiny_parts": invalid,
             "scene_rectangle_km2": round(extent.area / 1e6, 2), "scale": SCALE, "max_estimated_height_m": cmab_max,
             "osm_explicit_height_parts": len(osm_parts), "cmab_parts_replaced_by_osm": replaced,
             "max_height_in_model_m": max(f[0] for f in features),
             "height_note": "Explicit OSM heights where available; otherwise CMAB estimated height, not an official survey", "age_used_for_animation": False,
             "water_polygons": len(water), "route_segments": len(lines), "model_sha256": hashlib.sha256((DATA / "model.json").read_bytes()).hexdigest()}
    (DATA / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    (OUT / "data-verification.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    OUT = output_directory(protect_delivery=True)
    main()

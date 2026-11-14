"""Gera data/coast.json (linhas da costa recortadas) a partir do Natural Earth 50m.
Uso: python scripts/make_coast.py caminho/ne_50m_land.geojson   (ja vem gerado no projeto)"""
import json, sys
from pathlib import Path

LON0, LON1, LAT0, LAT1 = 28.0, 52.0, -27.0, -8.0
src = Path(sys.argv[1])
gj = json.loads(src.read_text())
lons, lats = [], []

def inside(x, y):
    return LON0 <= x <= LON1 and LAT0 <= y <= LAT1

def flush(seg):
    lons.extend([p[0] for p in seg] + [None])
    lats.extend([p[1] for p in seg] + [None])

def add_ring(ring):
    seg = []
    for x, y in ring:
        if inside(x, y):
            seg.append((x, y))
        elif seg:
            flush(seg); seg = []
    if seg:
        flush(seg)

for f in gj["features"]:
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        for ring in poly:
            add_ring(ring)

out = Path(__file__).resolve().parent.parent / "data" / "coast.json"
out.write_text(json.dumps({"lon": lons, "lat": lats}))
print("coast.json:", len(lons), "pontos")

"""Gera data/districts.json (limites administrativos simplificados + centroides).

  # DISTRITOS (recomendado) - corre no teu PC, com internet:
  python scripts/make_districts.py --source geoboundaries

  # PROVINCIAS (alternativa, ja vem gerado no projeto):
  python scripts/make_districts.py --source naturalearth --file ne_10m_admin_1_states_provinces.geojson

Fonte distritos: geoBoundaries (gbOpen, ADM2/ADM1 de Mocambique), via a API publica.
NOTA: o ramo geoboundaries NAO foi testado (o ambiente onde foi escrito nao alcanca o servidor).
Se a API mudar, descarrega o ADM2 'simplified' manualmente e usa --file ficheiro.geojson --source file.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import DATA, BBOX
from core.textfix import fix_name, unresolved

NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson"
GB_API = "https://www.geoboundaries.org/api/current/gbOpen/MOZ/{lvl}/"
PAD = 2.0   # graus alem da caixa do mapa


def simplify(ring, tol=0.015):
    """Douglas-Peucker iterativo."""
    pts = np.asarray(ring, float)
    n = len(pts)
    if n < 5:
        return pts
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg = pts[j] - pts[i]
        L = np.hypot(*seg)
        sub = pts[i + 1:j]
        if L == 0:
            d = np.hypot(*(sub - pts[i]).T)
        else:
            d = np.abs(seg[0] * (sub[:, 1] - pts[i][1]) - seg[1] * (sub[:, 0] - pts[i][0])) / L
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return pts[keep]


def area_centroid(ring):
    x, y = np.asarray(ring)[:, 0], np.asarray(ring)[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y2 - x2 * y
    a = cr.sum() / 2
    if abs(a) < 1e-12:
        return 0.0, float(x.mean()), float(y.mean())
    return abs(a), float(((x + x2) * cr).sum() / (6 * a)), float(((y + y2) * cr).sum() / (6 * a))


def inside(px, py, ring):
    r = np.asarray(ring)
    x1, y1, x2, y2 = r[:-1, 0], r[:-1, 1], r[1:, 0], r[1:, 1]
    cond = ((y1 > py) != (y2 > py)) & (px < (x2 - x1) * (py - y1) / np.where(y2 == y1, 1e-12, y2 - y1) + x1)
    return cond.sum() % 2 == 1


def read_json_bytes(b: bytes):
    try:
        return json.loads(b.decode("utf-8"))
    except UnicodeDecodeError:
        return json.loads(b.decode("latin-1"))


def outer_rings(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [p[0] for p in polys if p]


def build_unit(name, province, geom):
    rings = [simplify(r) for r in outer_rings(geom)]
    rings = [r for r in rings if len(r) >= 4]
    if not rings:
        return None
    big = max(rings, key=lambda r: area_centroid(r)[0])
    tot_area, lon, lat = area_centroid(big)
    if not (BBOX["lon_min"] - PAD <= lon <= BBOX["lon_max"] + PAD and BBOX["lat_min"] - PAD <= lat <= BBOX["lat_max"] + PAD):
        return None
    return {"name": fix_name(name), "province": fix_name(province), "lon": round(lon, 4), "lat": round(lat, 4),
            "area": tot_area, "rings": [np.round(r, 4).tolist() for r in rings]}


def from_naturalearth(path):
    if path and Path(path).exists():
        gj = read_json_bytes(Path(path).read_bytes())
    else:
        print("A descarregar Natural Earth 10m (~40 MB)...")
        gj = read_json_bytes(requests.get(NE_URL, timeout=300).content)
    feats = [f for f in gj["features"] if f["properties"].get("adm0_a3") == "MOZ"]
    units = [build_unit(f["properties"]["name"], f["properties"]["name"], f["geometry"]) for f in feats]
    units = [u for u in units if u]
    # NE tem dois "Maputo": o mais pequeno e a cidade
    mp = sorted([u for u in units if u["name"] == "Maputo"], key=lambda u: u["area"])
    if len(mp) == 2:
        mp[0]["name"] = "Maputo Cidade"; mp[0]["province"] = "Maputo Cidade"
        mp[1]["name"] = "Maputo (província)"
    return "provincia", units


def _gb_geojson(lvl):
    info = requests.get(GB_API.format(lvl=lvl), timeout=60).json()
    if isinstance(info, list):
        info = info[0]
    url = info.get("simplifiedGeometryGeoJSON") or info.get("gjDownloadURL")
    print(f"  {lvl}: {url}")
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return read_json_bytes(r.content)


def from_geoboundaries(file=None):
    print("A obter distritos (geoBoundaries ADM2)...")
    gj2 = read_json_bytes(Path(file).read_bytes()) if file else _gb_geojson("ADM2")
    prov = []
    try:
        gj1 = _gb_geojson("ADM1")
        for f in gj1["features"]:
            prov.append((f["properties"].get("shapeName", ""), outer_rings(f["geometry"])))
    except Exception as e:
        print("  ADM1 indisponivel, sem provincia:", e)
    units = []
    for f in gj2["features"]:
        u = build_unit(f["properties"].get("shapeName", "?"), "", f["geometry"])
        if not u:
            continue
        for pname, rings in prov:
            if any(inside(u["lon"], u["lat"], r) for r in rings):
                u["province"] = pname
                break
        units.append(u)
    return "distrito", units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["geoboundaries", "naturalearth", "file"], default="geoboundaries")
    ap.add_argument("--file")
    a = ap.parse_args()
    if a.source == "naturalearth":
        level, units = from_naturalearth(a.file)
    elif a.source == "file":
        level, units = from_geoboundaries(a.file)
    else:
        level, units = from_geoboundaries()
    for u in units:
        u.pop("area", None)
    out = DATA / "districts.json"
    out.write_text(json.dumps({"level": level, "units": units}, ensure_ascii=False), encoding="utf-8")
    bad = unresolved([u["name"] for u in units] + [u["province"] for u in units])
    if bad:
        print(f"ATENCAO: {len(bad)} nomes com caracteres por recuperar (marcados com '?'):")
        for n in bad:
            print("  ", n)
        print("Corrige em data/name_fixes.json, ex.: {\"Ch?kw?\": \"Chókwè\"}")
    print(f"{len(units)} unidades ({level}) -> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

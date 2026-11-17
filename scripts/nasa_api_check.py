"""Prova de proveniencia NASA, por APIs OFICIAIS e SEM chave (so precisa de internet, uma vez).

  python scripts/nasa_api_check.py

  1) CMR (NASA Earthdata): quantos ficheiros GPM IMERG e MUR25 (mar) existem para 1-12 mar 2023 sobre o Canal.
  2) EONET v3 (NASA): o evento "Freddy" (categoria severeStorms), com o numero de posicoes e datas.

Guarda data/nasa_provenance.json. A app SO le este ficheiro (nunca faz rede), por isso continua offline.

Equivalentes numa linha (HTTP):
  curl "https://eonet.gsfc.nasa.gov/api/v3/events?category=severeStorms&status=all&start=2023-02-01&end=2023-03-31"
  curl -sI "https://cmr.earthdata.nasa.gov/search/granules.json?short_name=GPM_3IMERGDF&version=07&temporal=2023-03-01T00:00:00Z,2023-03-12T23:59:59Z&bounding_box=30,-25,50,-10&page_size=1" | grep -i cmr-hits
Descarregar os ficheiros (isto SIM precisa de conta/token Earthdata, gratuito):
  curl -L -H "Authorization: Bearer $EARTHDATA_TOKEN" -O "<url do granulo>"
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import BBOX, DATA, START, END

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
EONET = "https://eonet.gsfc.nasa.gov/api/v3/events"
IMERG = {"short_name": "GPM_3IMERGDF", "version": "07"}   # diario, Final: o produto que o fetch usa
MUR25 = {"short_name": "MUR25-JPL-L4-GLOB-v04.2"}          # temperatura do mar NASA JPL, 0.25 graus, diario


def cmr_granules(start=START, end=END, product=IMERG):
    params = {**product, "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
              "bounding_box": f"{BBOX['lon_min']},{BBOX['lat_min']},{BBOX['lon_max']},{BBOX['lat_max']}",
              "page_size": 1}
    out = {"request": requests.Request("GET", CMR, params=params).prepare().url}
    r = requests.get(CMR, params=params, timeout=60)
    r.raise_for_status()
    out["hits"] = int(r.headers.get("CMR-Hits", 0))
    entries = r.json().get("feed", {}).get("entry", [])
    out["first_granule"] = entries[0].get("title") if entries else None
    out["collection"] = product["short_name"] + (f" v{product['version']}" if product.get("version") else "")
    return out


def eonet_freddy(start="2023-02-01", end="2023-03-31", name="freddy"):
    params = {"category": "severeStorms", "status": "all", "start": start, "end": end}
    r = requests.get(EONET, params=params, timeout=60)
    r.raise_for_status()
    out = {"request": requests.Request("GET", EONET, params=params).prepare().url, "events": []}
    for e in r.json().get("events", []):
        if name in e.get("title", "").lower():
            g = e.get("geometry", [])
            dates = sorted(x["date"] for x in g if "date" in x)
            out["events"].append({"id": e["id"], "title": e["title"], "link": e.get("link"),
                                  "positions": len(g), "first": dates[0] if dates else None,
                                  "last": dates[-1] if dates else None,
                                  "sources": [s.get("id") for s in e.get("sources", [])]})
    return out


def main():
    res = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errors": []}
    for key, fn in (("cmr", cmr_granules), ("cmr_sst", lambda: cmr_granules(product=MUR25)), ("eonet", eonet_freddy)):
        try:
            res[key] = fn()
            print(f"{key.upper()}: ok")
        except Exception as e:
            res["errors"].append(f"{key}: {e}")
            print(f"{key.upper()}: FALHOU -> {e}")
    if "cmr" not in res and "eonet" not in res:
        sys.exit("Nada obtido; nao sobrescrevi data/nasa_provenance.json")
    (DATA / "nasa_provenance.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

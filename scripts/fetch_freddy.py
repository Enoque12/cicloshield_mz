"""Descarrega e guarda LOCALMENTE os dados reais do Freddy (corre uma vez, com internet).

  python scripts/fetch_freddy.py                # trajetoria + SST (+ chuva se houver credenciais)
  python scripts/fetch_freddy.py --skip-rain

Fontes:
  * Trajetoria real: IBTrACS v04r01 (NOAA/NCEI), bacia Indico Sul.
  * SST: GHRSST MUR L4 (NASA JPL) via ERDDAP da NOAA CoastWatch (sem login), subamostrado a 0.1 grau (opcional: so funciona se coastwatch.pfeg.noaa.gov for acessivel).
  * Chuva: GPM IMERG diario (NASA GES DISC) via `earthaccess`.
    Precisa de EARTHDATA_USERNAME / EARTHDATA_PASSWORD (conta gratuita). Opcional.
  * Previsao: NAO ha download limpo. Preenche data/forecast.csv a mao (ver README).

NOTA: este script NAO foi testado contra os servidores reais. Se algum URL/variavel falhar,
a mensagem de erro indica qual; corrige e volta a correr (cada fonte e independente).
"""
import argparse
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import DATA, RAW, BBOX, START, END

IBTRACS_URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-"
               "stewardship-ibtracs/v04r01/access/csv/ibtracs.SI.list.v04r01.csv")
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.nc"


def get(url, tries=2, timeout=60):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code != 200:
                body = r.text[:300].replace("\n", " ")
                raise RuntimeError(f"HTTP {r.status_code}: {body}")
            return r
        except Exception as e:
            last = e
            print(f"  tentativa {i + 1}/{tries} falhou: {e}")
            time.sleep(3)
    raise RuntimeError(f"Falhou: {url[:100]}... | ultimo erro: {last}")

def fetch_track(start, end):
    print("[1/3] Trajetoria IBTrACS...")
    df = pd.read_csv(BytesIO(get(IBTRACS_URL).content), skiprows=[1], low_memory=False)
    df = df[df["NAME"].astype(str).str.upper() == "FREDDY"].copy()
    df["time"] = pd.to_datetime(df["ISO_TIME"])
    df = df[df["time"] >= "2023-01-01"]
    if df.empty:
        raise RuntimeError("Freddy 2023 nao encontrado no ficheiro IBTrACS SI.")
    wcols = [c for c in ("REUNION_WIND", "WMO_WIND", "USA_WIND") if c in df.columns]
    wind = df[wcols].apply(pd.to_numeric, errors="coerce").bfill(axis=1).iloc[:, 0]
    out = pd.DataFrame({"time": df["time"], "lat": pd.to_numeric(df["LAT"]),
                        "lon": pd.to_numeric(df["LON"]), "wind_kt": wind})
    out = out[(out["time"] >= start) & (out["time"] <= pd.Timestamp(end) + pd.Timedelta(days=1))]
    out = out.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    out.to_csv(DATA / "track.csv", index=False)
    print(f"  {len(out)} pontos guardados em data/track.csv")


def _erddap_nc(url, name):
    r = get(url)
    tmp = RAW / name
    tmp.write_bytes(r.content)
    with xr.open_dataset(tmp) as ds:
        return ds.load()


def _fetch_sst_mur(start, end, stride):
    """MUR (NASA JPL) via ERDDAP: UM pedido por dia (mais leve e tolerante a falhas)."""
    days = pd.date_range(start, end, freq="D")
    parts = []
    for d in days:
        day = d.strftime("%Y-%m-%d")
        q = (f"analysed_sst[({day}T09:00:00Z)]"
             f"[({BBOX['lat_min']}):{stride}:({BBOX['lat_max']})]"
             f"[({BBOX['lon_min']}):{stride}:({BBOX['lon_max']})]")
        try:
            ds = _erddap_nc(f"{ERDDAP}?{quote(q, safe='')}", f"mur_{day}.nc")
        except Exception as e:
            print(f"  dia {day} falhou, a saltar: {e}")
            continue
        da = ds["analysed_sst"].rename({"latitude": "lat", "longitude": "lon"})
        da = da.assign_coords(time=[pd.Timestamp(day)])
        parts.append(da)
        print(f"  {day} ok")
    if not parts:
        raise RuntimeError("MUR: nenhum dia foi obtido.")
    return xr.concat(parts, dim="time")


OISST_BUCKET = "noaa-cdr-sea-surface-temp-optimum-interpolation-pds"


def _fetch_sst_oisst_s3(start, end):
    """NOAA OISST v2.1 (AVHRR, 0.25 grau) no S3 anonimo: um ficheiro NetCDF global por dia.
    E NOAA, NAO NASA: dizer isso na apresentacao."""
    import s3fs
    fs = s3fs.S3FileSystem(anon=True)
    parts = []
    for d in pd.date_range(start, end, freq="D"):
        ymd = d.strftime("%Y%m%d")
        key = f"{OISST_BUCKET}/data/v2.1/avhrr/{ymd[:6]}/oisst-avhrr-v02r01.{ymd}.nc"
        local = RAW / f"oisst_{ymd}.nc"
        try:
            if not local.exists():
                fs.get(key, str(local))
            with xr.open_dataset(local) as ds:
                da = (ds["sst"].isel(zlev=0, drop=True)
                      .sel(lat=slice(BBOX["lat_min"], BBOX["lat_max"]),
                           lon=slice(BBOX["lon_min"], BBOX["lon_max"]))
                      .load())
            parts.append(da.assign_coords(time=[pd.Timestamp(d)]))
            print(f"  {ymd} ok")
        except Exception as e:
            print(f"  dia {ymd} falhou, a saltar: {e}")
    if not parts:
        raise RuntimeError("OISST: nenhum dia foi obtido.")
    return xr.concat(parts, dim="time")


def fetch_sst(start, end, stride=10, source="oisst"):
    print(f"[2/3] SST ({source})...")
    da = _fetch_sst_oisst_s3(start, end) if source == "oisst" else _fetch_sst_mur(start, end, stride)
    mean_val = float(da.mean().compute().item())
    if mean_val > 200:                 # Kelvin -> Celsius
        da = da - 273.15
    da.name = "sst"
    da.to_dataset().to_netcdf(DATA / "sst.nc")
    print(f"  SST ({source}) {dict(da.sizes)} guardada em data/sst.nc")
    return source

ZARR_RAIN = "s3://us-west-2.opendata.source.coop/bkr/imerg/gpm_final.zarr"


def fetch_rain_zarr(start, end, path=ZARR_RAIN):
    """GPM IMERG Final (meia-hora, 0.1 grau) do Zarr publico do Source Cooperative. Sem login.
    Fonte de terceiros com dados NASA: citar assim na apresentacao."""
    print("[3/3] Chuva GPM IMERG (Zarr Source Coop, sem login)...")
    opts = {"anon": True} if str(path).startswith("s3://") else {}
    ds = xr.open_zarr(path, storage_options=opts) if opts else xr.open_zarr(path)
    da = ds["precipitation"]
    units = str(da.attrs.get("units", "?"))
    print(f"  unidades declaradas: {units}")
    sub = da.sel(time=slice(start, end),
                 latitude=slice(BBOX["lat_min"], BBOX["lat_max"]),
                 longitude=slice(BBOX["lon_min"], BBOX["lon_max"])).load()
    print(f"  {sub.sizes['time']} passos de tempo carregados")
    if "mm/h" not in units.replace("/hr", "/h").replace(" ", "") and units != "?":
        print("  AVISO: unidades nao sao mm/h; confirma antes de somar!")
    acc = (sub * 0.5).sum("time", skipna=True)       # mm/h x 0.5 h por passo = mm
    acc = acc.rename({"latitude": "lat", "longitude": "lon"}).transpose("lat", "lon")
    acc.name = "rain_mm"
    acc.to_dataset().to_netcdf(DATA / "rain.nc")
    print(f"  chuva acumulada: max {float(acc.max()):.0f} mm, guardada em data/rain.nc")


def fetch_rain(start, end):
    print("[3/3] Chuva GPM IMERG (opcional)...")
    if not (os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD")):
        print("  sem EARTHDATA_USERNAME/PASSWORD -> chuva ignorada (a app funciona sem ela).")
        return
    import earthaccess
    earthaccess.login(strategy="environment")
    res = earthaccess.search_data(short_name="GPM_3IMERGDL", version="07",
                                  temporal=(start, end),
                                  bounding_box=(BBOX["lon_min"], BBOX["lat_min"],
                                                BBOX["lon_max"], BBOX["lat_max"]))
    files = earthaccess.download(res, str(RAW))
    ds = xr.open_mfdataset(files, combine="by_coords")
    p = ds["precipitation"].sel(lat=slice(BBOX["lat_min"], BBOX["lat_max"]),
                                lon=slice(BBOX["lon_min"], BBOX["lon_max"]))
    acc = p.sum("time", skipna=True).transpose("lat", "lon").load()
    acc.name = "rain_mm"
    acc.to_dataset().to_netcdf(DATA / "rain.nc")
    print("  chuva acumulada guardada em data/rain.nc")


def ensure_forecast_template():
    p = DATA / "forecast.csv"
    if not p.exists():
        p.write_text("issued,valid,lat,lon,wind_kt\n")
        print("Criado data/forecast.csv vazio (preencher a mao com posicoes previstas).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument("--skip-rain", action="store_true")
    ap.add_argument("--sst-source", choices=["oisst", "mur"], default="oisst")
    a = ap.parse_args()
    DATA.mkdir(exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
    fetch_track(a.start, a.end)
    sst_src = fetch_sst(a.start, a.end, source=a.sst_source)
    if not a.skip_rain:
        try:
            fetch_rain_zarr(a.start, a.end)
        except Exception as e:
            print("  Zarr falhou:", e, "-> a tentar Earthdata...")
            try:
                fetch_rain(a.start, a.end)
            except Exception as e2:
                print("  chuva falhou (nao bloqueia):", e2)
    ensure_forecast_template()
    (DATA / "meta.json").write_text(json.dumps({
        "demo": False, "event": "Ciclone Freddy (2023)",
        "sources": "IBTrACS v04r01 (NOAA); " + ("NOAA OISST v2.1 (AVHRR, 0.25 graus)" if sst_src == "oisst" else "GHRSST MUR L4 (NASA JPL)") + "; GPM IMERG (NASA, via Source Coop)"},
        ensure_ascii=False, indent=2))
    print("Pronto. Corre: streamlit run app.py")


if __name__ == "__main__":
    main()
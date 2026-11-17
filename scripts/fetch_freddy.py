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


def _earthdata_login():
    """Login Earthdata: variaveis de ambiente, ou ~/.netrc, ou pergunta uma vez e guarda no ~/.netrc."""
    import earthaccess
    from core.credentials import load_credentials
    if load_credentials():
        auth = earthaccess.login(strategy="environment")
    else:
        try:
            auth = earthaccess.login(strategy="netrc")
        except Exception:
            auth = earthaccess.login(strategy="interactive", persist=True)
    if not getattr(auth, "authenticated", True):
        raise RuntimeError("Login Earthdata falhou. Confirma utilizador/palavra-passe.")


def _fetch_sst_mur_nasa(start, end):
    """NASA JPL PO.DAAC, MUR25-JPL-L4-GLOB-v04.2 (GHRSST MUR, 0.25 graus, diario). Precisa de conta Earthdata."""
    import earthaccess
    _earthdata_login()
    res = earthaccess.search_data(short_name="MUR25-JPL-L4-GLOB-v04.2", temporal=(start, f"{end}T23:59:59"))
    if not res:
        raise RuntimeError("CMR nao devolveu granulos MUR25 v04.2 para o periodo.")
    print(f"  {len(res)} ficheiros MUR25 encontrados; a descarregar...")
    files = earthaccess.download(res, str(RAW))
    parts = []
    for f in sorted(files):
        with xr.open_dataset(f) as ds:
            da = ds["analysed_sst"].sel(lat=slice(BBOX["lat_min"], BBOX["lat_max"]),
                                        lon=slice(BBOX["lon_min"], BBOX["lon_max"])).load()
        parts.append(da.assign_coords(time=pd.to_datetime(da["time"].values).normalize()))
    return xr.concat(parts, dim="time").sel(time=slice(start, end))


def fetch_sst(start, end, stride=10, source="oisst"):
    print(f"[2/3] SST ({source})...")
    if source == "oisst":
        da = _fetch_sst_oisst_s3(start, end)
    elif source == "mur-nasa":
        da = _fetch_sst_mur_nasa(start, end)
    else:
        da = _fetch_sst_mur(start, end, stride)
    mean_val = float(da.mean().compute().item())
    if mean_val > 200:     
        da.name = "sst"
    da.to_dataset().to_netcdf(DATA / "sst.nc")
    print(f"  SST ({source}) {dict(da.sizes)} guardada em data/sst.nc")
    return source

ZARR_RAIN = "s3://us-west-2.opendata.source.coop/bkr/imerg/gpm_final.zarr"


def _check_rain(acc, label):
    """Recusa chuva sem dados: soma de NaN daria 0 mm e enganava a app."""
    vals = acc.values
    n = int(np.isfinite(vals).sum())
    mx = float(np.nanmax(vals)) if n else float("nan")
    if n == 0 or not mx > 0:
        raise RuntimeError(f"{label}: sem chuva valida no periodo/area (celulas validas={n}, max={mx}). "
                           "Nao guardei rain.nc.")
    print(f"  chuva acumulada: max {mx:.0f} mm; {n} celulas validas")


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
    if int(np.isfinite(sub.values).sum()) == 0:
        raise RuntimeError("O Zarr tem o eixo do tempo mas todos os valores sao NaN neste periodo/area "
                           "(espelho incompleto). Nao guardei rain.nc.")
    acc = (sub * 0.5).sum("time", skipna=True, min_count=1)   # mm/h x 0.5 h por passo = mm
    acc = acc.rename({"latitude": "lat", "longitude": "lon"}).transpose("lat", "lon")
    acc.name = "rain_mm"
    _check_rain(acc, "Zarr")
    acc.to_dataset().to_netcdf(DATA / "rain.nc")
    print("  guardada em data/rain.nc")
    return True


def fetch_rain(start, end):
    """Via OFICIAL NASA (Earthdata/GES DISC): pesquisa CMR + download autenticado. Precisa de conta gratuita."""
    print("[3/3] Chuva GPM IMERG via NASA Earthdata (CMR + download)...")
    import earthaccess
    _earthdata_login()
    res = earthaccess.search_data(short_name="GPM_3IMERGDF", version="07",
                                  temporal=(start, f"{end}T23:59:59"),
                                  bounding_box=(BBOX["lon_min"], BBOX["lat_min"],
                                                BBOX["lon_max"], BBOX["lat_max"]))
    if not res:
        raise RuntimeError("CMR nao devolveu granulos GPM_3IMERGDF v07 para o periodo/area.")
    files = earthaccess.download(res, str(RAW))
    parts = []
    for f in sorted(files):          # um de cada vez: nao precisa de dask
        with xr.open_dataset(f) as ds:
            parts.append(ds["precipitation"].sel(lat=slice(BBOX["lat_min"], BBOX["lat_max"]),
                                                 lon=slice(BBOX["lon_min"], BBOX["lon_max"])).load())
    print(f"  {len(parts)} ficheiros NASA lidos (mm/dia)")
    acc = xr.concat(parts, dim="time").sum("time", skipna=True, min_count=1).transpose("lat", "lon")
    acc.name = "rain_mm"
    _check_rain(acc, "GPM NASA")
    acc.to_dataset().to_netcdf(DATA / "rain.nc")
    print("  guardada em data/rain.nc")
    return True


def ensure_forecast_template():
    p = DATA / "forecast.csv"
    if not p.exists():
        p.write_text("issued,valid,lat,lon,wind_kt\n")
        print("Criado data/forecast.csv vazio (preencher a mao com posicoes previstas).")


def clean_stale(skip_rain):
    """Evita misturar dados novos com ficheiros antigos ou SINTETICOS da demonstracao."""
    from core.textfix import read_text
    mp = DATA / "meta.json"
    old_demo = False
    if mp.exists():
        try:
            old_demo = bool(json.loads(read_text(mp)).get("demo"))
        except Exception:
            pass
    if old_demo:
        for f in ("rain.nc", "forecast.csv"):
            if (DATA / f).exists():
                (DATA / f).unlink()
                print(f"  removido data/{f} (era sintetico, da demonstracao)")
    elif not skip_rain and (DATA / "rain.nc").exists():
        (DATA / "rain.nc").unlink()
        print("  removido data/rain.nc antigo (vai ser refeito)")
    if skip_rain and (DATA / "rain.nc").exists():
        print("  AVISO: --skip-rain: o rain.nc existente NAO foi atualizado.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument("--skip-rain", action="store_true")
    ap.add_argument("--sst-source", choices=["oisst", "mur-nasa", "mur"], default="oisst")
    a = ap.parse_args()
    DATA.mkdir(exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
    clean_stale(a.skip_rain)
    fetch_track(a.start, a.end)
    sst_src = fetch_sst(a.start, a.end, source=a.sst_source)
    rain_src = None
    if not a.skip_rain:
        try:   # 1.o via oficial NASA (se houver credenciais Earthdata)
            if fetch_rain(a.start, a.end):
                rain_src = "NASA Earthdata (GES DISC)"
        except Exception as e:
            print("  via NASA falhou:", e)
        if rain_src is None:   # 2.o espelho publico Zarr (dados NASA, de terceiros)
            try:
                if fetch_rain_zarr(a.start, a.end):
                    rain_src = "Source Cooperative Zarr (espelho de dados NASA GPM IMERG)"
            except Exception as e:
                print("  chuva falhou (nao bloqueia):", e)
    ensure_forecast_template()
    sst_label = {"oisst": "NOAA OISST v2.1 (AVHRR, 0.25 graus)",
                 "mur-nasa": "GHRSST MUR L4 v4.2, 0.25 graus (NASA JPL PO.DAAC)",
                 "mur": "GHRSST MUR L4 (NASA JPL, via ERDDAP)"}[sst_src]
    (DATA / "meta.json").write_text(json.dumps({
        "demo": False, "event": "Ciclone Freddy (2023)", "period": [a.start, a.end],
        "sst_source": sst_label, "rain_source": rain_src,
        "sources": "IBTrACS v04r01 (NOAA); " + sst_label + "; GPM IMERG (NASA)"
                   + (f" via {rain_src}" if rain_src else " [chuva nao carregada]")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("Pronto. Corre: streamlit run app.py")


if __name__ == "__main__":
    main()

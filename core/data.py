"""Leitura de dados LOCAIS. A app nunca faz chamadas de rede."""
import json
import numpy as np
import pandas as pd
import xarray as xr
from .config import DATA
from .textfix import fix_name, read_text


def load_meta() -> dict:
    p = DATA / "meta.json"
    return json.loads(read_text(p)) if p.exists() else {}


def data_ready() -> bool:
    return all((DATA / f).exists() for f in ("sst.nc", "track.csv"))


def load_sst() -> xr.DataArray:
    """sst em graus C, dims (time, lat, lon)."""
    with xr.open_dataset(DATA / "sst.nc") as ds:
        return ds["sst"].load()


def load_rain():
    p = DATA / "rain.nc"
    if not p.exists():
        return None
    with xr.open_dataset(p) as ds:
        return ds["rain_mm"].load()


def load_track() -> pd.DataFrame:
    """colunas: time, lat, lon, wind_kt"""
    return pd.read_csv(DATA / "track.csv", parse_dates=["time"], encoding="utf-8")


def load_forecast():
    """colunas: issued, valid, lat, lon, wind_kt (ou None se vazio/inexistente)"""
    p = DATA / "forecast.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["issued", "valid"])
    return df if len(df) else None


def load_coast():
    p = DATA / "coast.json"
    if not p.exists():
        return None
    return json.loads(read_text(p))


def load_districts():
    """{'level': 'distrito'|'provincia', 'units': [...]} com aneis em numpy (rings_np), ou None."""
    p = DATA / "districts.json"
    if not p.exists():
        return None
    j = json.loads(read_text(p))
    for u in j["units"]:
        u["name"] = fix_name(u["name"])
        u["province"] = fix_name(u.get("province", ""))
        u["rings_np"] = [np.asarray(r, float) for r in u["rings"]]
    return j


def load_provenance():
    """Resultado de scripts/nasa_api_check.py (APIs oficiais NASA), ou None."""
    p = DATA / "nasa_provenance.json"
    return json.loads(read_text(p)) if p.exists() else None


def _d(t) -> str:
    return pd.Timestamp(t).strftime("%d/%m/%Y")


def data_summary(meta, sst, rain, track, fc):
    """Tabela (lista de dicts) com fonte, periodo e origem de cada dado + frase-resumo."""
    sst_t = pd.to_datetime(sst["time"].values)
    src = meta.get("sources", "")
    sst_src = meta.get("sst_source") or ("NOAA OISST v2.1" if "OISST" in src else "GHRSST MUR (NASA JPL)" if "MUR" in src else "—")
    per = meta.get("period")
    rows = [
        {"Dado": "Trajetória real", "Fonte": "IBTrACS v04r01", "Período": f"{_d(track['time'].min())} a {_d(track['time'].max())} ({len(track)} posições)", "Origem": "NOAA"},
        {"Dado": "Temperatura do mar", "Fonte": sst_src, "Período": f"{_d(sst_t.min())} a {_d(sst_t.max())} ({len(sst_t)} dias)", "Origem": "NASA" if "MUR" in sst_src else "NOAA"},
        {"Dado": "Chuva acumulada", "Fonte": meta.get("rain_source") or "GPM IMERG", "Período": f"{_d(per[0])} a {_d(per[1])}" if per else "mesmo período da temperatura do mar", "Origem": "NASA"} if rain is not None
        else {"Dado": "Chuva acumulada", "Fonte": "—", "Período": "não carregada", "Origem": "—"},
    ]
    if fc is not None:
        iss = ", ".join(sorted({pd.Timestamp(x).strftime("%d/%m %Hh UTC") for x in fc["issued"]}))
        rows.append({"Dado": "Previsão da trajetória", "Fonte": "Avisos públicos, introduzidos à mão",
                     "Período": f"emitida em {iss}; válida de {_d(fc['valid'].min())} a {_d(fc['valid'].max())}", "Origem": "Agência do aviso"})
    else:
        rows.append({"Dado": "Previsão da trajetória", "Fonte": "—", "Período": "ainda não carregada", "Origem": "—"})
    headline = f"Período dos dados: {_d(sst_t.min())} a {_d(sst_t.max())}" + (
        f" · previsão emitida em {iss}" if fc is not None else " · sem previsão carregada")
    return rows, headline

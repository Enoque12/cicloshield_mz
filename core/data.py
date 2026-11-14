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

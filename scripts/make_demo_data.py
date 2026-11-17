"""Gera dados SINTETICOS (DEMO) com o mesmo formato dos dados reais,
para a app correr ja. NAO sao dados do Freddy. Substitui com fetch_freddy.py."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import DATA, BBOX

rng = np.random.default_rng(7)
DATA.mkdir(exist_ok=True)

lat = np.round(np.arange(BBOX["lat_min"], BBOX["lat_max"] + 0.01, 0.1), 2)
lon = np.round(np.arange(BBOX["lon_min"], BBOX["lon_max"] + 0.01, 0.1), 2)
times = pd.date_range("2023-03-01", "2023-03-12", freq="D")
LON, LAT = np.meshgrid(lon, lat)

base = 30.8 - 0.28 * (np.abs(LAT) - 10)                       # mais frio para sul
patch = 1.6 * np.exp(-(((LON - 41) / 4) ** 2 + ((LAT + 18) / 2.5) ** 2))  # mancha quente
sst = np.stack([base + patch + 0.15 * rng.standard_normal(base.shape) for _ in times])
xr.Dataset({"sst": (("time", "lat", "lon"), sst.astype("float32"))},
           coords={"time": times, "lat": lat, "lon": lon}).to_netcdf(DATA / "sst.nc")

rain = 380 * np.exp(-(((LON - 36.5) / 2.2) ** 2 + ((LAT + 18) / 1.6) ** 2)) + 20 * rng.random(base.shape)
xr.Dataset({"rain_mm": (("lat", "lon"), rain.astype("float32"))},
           coords={"lat": lat, "lon": lon}).to_netcdf(DATA / "rain.nc")

tt = pd.date_range("2023-03-04", "2023-03-12", freq="6h")
n = len(tt)
x = np.linspace(0, 1, n)
tlon = 44 - 7.3 * x ** 0.9
tlat = -20 + 2.0 * x + 0.6 * np.sin(x * 5)
wind = 55 + 45 * np.sin(np.clip(x * 1.15, 0, 1) * np.pi * 0.85) + 5 * (x > 0.85) * 0
pd.DataFrame({"time": tt, "lat": tlat, "lon": tlon, "wind_kt": np.round(wind)}).to_csv(DATA / "track.csv", index=False)

issued = pd.Timestamp("2023-03-08 00:00")
fv = pd.date_range(issued + pd.Timedelta(hours=12), issued + pd.Timedelta(hours=72), freq="12h")
real = pd.read_csv(DATA / "track.csv", parse_dates=["time"])
fl = np.interp(fv.astype("int64"), real["time"].astype("int64"), real["lat"])
fo = np.interp(fv.astype("int64"), real["time"].astype("int64"), real["lon"])
lead = np.arange(1, len(fv) + 1)
pd.DataFrame({"issued": issued, "valid": fv, "lat": fl + 0.25 * lead, "lon": fo + 0.35 * lead,
              "wind_kt": 75, "source": "SINTETICO (DEMO)"}).to_csv(DATA / "forecast.csv", index=False)

(DATA / "meta.json").write_text(json.dumps({
    "demo": True, "event": "Ciclone Freddy (2023) - DADOS SINTETICOS DE DEMONSTRACAO",
    "sources": "sinteticos"}, ensure_ascii=False, indent=2))
print("Dados DEMO gerados em", DATA)

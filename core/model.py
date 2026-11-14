"""Modelo SIMPLES e transparente. Ilustrativo, nao operacional."""
import numpy as np
import pandas as pd
from .config import GENESIS_SST

KT_TO_KMH = 1.852

# (limiar em nos, nome). Escala Saffir-Simpson aplicada ao vento do dataset.
# Nota: agencias usam periodos de media diferentes (10 min vs 1 min).
CATEGORIES = [
    (137, "Categoria 5"), (113, "Categoria 4"), (96, "Categoria 3"),
    (83, "Categoria 2"), (64, "Categoria 1"),
    (34, "Tempestade tropical"), (0, "Depressao tropical"),
]


def category(wind_kt: float) -> str:
    for thr, name in CATEGORIES:
        if wind_kt >= thr:
            return name
    return CATEGORIES[-1][1]


def weakened_wind(vmax_kt: float, delta_sst: float, sens_kt_per_c: float = 6.0) -> float:
    """Vento maximo apos variar a SST em `delta_sst` (negativo = mar mais frio).
    Relacao LINEAR com sensibilidade configuravel (hipotese a validar na literatura,
    ex.: teoria de intensidade potencial). Piso de 20 kt."""
    return max(vmax_kt + sens_kt_per_c * delta_sst, 20.0)


def below_genesis(sst_c: float) -> bool:
    return sst_c < GENESIS_SST


def local_sst(sst_da, time, lat, lon, r=1.5) -> float:
    """SST media numa janela de +-r graus em torno de (lat, lon), no dia mais proximo."""
    sl = sst_da.sel(time=time, method="nearest")
    box = sl.sel(lat=slice(lat - r, lat + r), lon=slice(lon - r, lon + r))
    val = float(box.mean(skipna=True))
    return val if np.isfinite(val) else float("nan")


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def track_errors(track: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    """Erro (km) entre posicao prevista e posicao real interpolada no mesmo instante."""
    t = track.sort_values("time")
    tt = t["time"].astype("int64").to_numpy().astype(float)
    out = forecast.copy()
    v = out["valid"].astype("int64").to_numpy().astype(float)
    ok = (v >= tt.min()) & (v <= tt.max())
    out = out[ok].copy()
    v = v[ok]
    rl = np.interp(v, tt, t["lat"].to_numpy())
    ro = np.interp(v, tt, t["lon"].to_numpy())
    out["real_lat"], out["real_lon"] = rl, ro
    out["err_km"] = haversine_km(out["lat"].to_numpy(), out["lon"].to_numpy(), rl, ro)
    out["lead_h"] = (out["valid"] - out["issued"]).dt.total_seconds() / 3600
    return out

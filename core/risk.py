"""Risco por unidade administrativa (distrito ou provincia) e alerta guiado pela margem de erro.

Ideia central: a previsao tem erro. Em vez de avisar so quem esta dentro do raio de impacto da
trajetoria PREVISTA, alargamos a zona pelo erro historico tipico (a margem).
  Nivel 3 Impacto direto : distancia <= R
  Nivel 2 Alerta         : distancia <= R + margem
  Nivel 1 Vigilancia     : distancia <= R + 2*margem
Distancia = menor distancia (km) entre a trajetoria e o POLIGONO da unidade (0 se passar dentro).
"""
import numpy as np
import pandas as pd

KM_LON, KM_LAT = 111.32, 110.57   # km por grau (aprox. equiretangular)
LEVEL_NAME = {3: "Impacto direto", 2: "Alerta", 1: "Vigilância", 0: "Sem alerta"}


def _xy(lon, lat, lat0):
    return np.asarray(lon, float) * np.cos(np.radians(lat0)) * KM_LON, np.asarray(lat, float) * KM_LAT


def _secs(s: pd.Series) -> np.ndarray:
    return (s - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()


def densify(df: pd.DataFrame, tcol: str, start=None, end=None, step_h: float = 1.0) -> pd.DataFrame:
    """Interpola a trajetoria de hora a hora. Devolve colunas time, lat, lon (vazio se sem sobreposicao)."""
    d = df.sort_values(tcol)
    t = _secs(d[tcol])
    if len(d) == 1:
        return pd.DataFrame({"time": [d[tcol].iloc[0]], "lat": [d["lat"].iloc[0]], "lon": [d["lon"].iloc[0]]})
    lo = t.min() if start is None else max(t.min(), (pd.Timestamp(start) - pd.Timestamp("1970-01-01")).total_seconds())
    hi = t.max() if end is None else min(t.max(), (pd.Timestamp(end) - pd.Timestamp("1970-01-01")).total_seconds())
    if hi < lo:
        return pd.DataFrame(columns=["time", "lat", "lon"])
    g = np.arange(lo, hi + 1, step_h * 3600.0)
    return pd.DataFrame({"time": pd.to_datetime(g, unit="s"),
                         "lat": np.interp(g, t, d["lat"].to_numpy()),
                         "lon": np.interp(g, t, d["lon"].to_numpy())})


def _inside(px, py, ring):
    x1, y1, x2, y2 = ring[:-1, 0], ring[:-1, 1], ring[1:, 0], ring[1:, 1]
    dy = np.where(y2 == y1, 1e-12, y2 - y1)
    pyc, pxc = py[:, None], px[:, None]
    cond = ((y1 > pyc) != (y2 > pyc)) & (pxc < (x2 - x1) * (pyc - y1) / dy + x1)
    return cond.sum(axis=1) % 2 == 1


def dist_to_unit_km(lons, lats, unit) -> np.ndarray:
    """Distancia (km) de cada ponto ao poligono da unidade; 0 se estiver dentro."""
    lat0 = unit["lat"]
    px, py = _xy(lons, lats, lat0)
    best = np.full(px.shape, np.inf)
    for r in unit["rings_np"]:
        rx, ry = _xy(r[:, 0], r[:, 1], lat0)
        x1, y1, x2, y2 = rx[:-1], ry[:-1], rx[1:], ry[1:]
        dx, dy = x2 - x1, y2 - y1
        L2 = np.where(dx * dx + dy * dy == 0, 1e-12, dx * dx + dy * dy)
        t = np.clip(((px[:, None] - x1) * dx + (py[:, None] - y1) * dy) / L2, 0, 1)
        d = np.hypot(px[:, None] - (x1 + t * dx), py[:, None] - (y1 + t * dy)).min(axis=1)
        d = np.where(_inside(px, py, np.column_stack([rx, ry])), 0.0, d)
        best = np.minimum(best, d)
    return best


def rain_in_unit(rain, unit) -> float:
    """Chuva acumulada media (mm) nas celulas cujo centro cai dentro da unidade."""
    if rain is None:
        return float("nan")
    allp = np.vstack(unit["rings_np"])
    sub = rain.sel(lat=slice(allp[:, 1].min() - 0.1, allp[:, 1].max() + 0.1),
                   lon=slice(allp[:, 0].min() - 0.1, allp[:, 0].max() + 0.1))
    if sub.size:
        LON, LAT = np.meshgrid(sub["lon"].values, sub["lat"].values)
        lon_f, lat_f = LON.ravel(), LAT.ravel()
        px, py = _xy(lon_f, lat_f, unit["lat"])
        mask = np.zeros(px.shape, bool)
        for r in unit["rings_np"]:
            rx, ry = _xy(r[:, 0], r[:, 1], unit["lat"])
            mask |= _inside(px, py, np.column_stack([rx, ry]))
        vals = sub.values.ravel()[mask]
        if vals.size:
            return float(np.nanmean(vals))
    return float(rain.sel(lat=unit["lat"], lon=unit["lon"], method="nearest"))


def margin_at_lead(err_df, lead_h: float, default: float = 100.0) -> float:
    """Erro medio (km) da previsao ao prazo `lead_h`, interpolado a partir do historico."""
    if err_df is None or len(err_df) == 0:
        return default
    g = err_df.groupby(err_df["lead_h"].round(0))["err_km"].mean().sort_index()
    return float(np.interp(lead_h, g.index.to_numpy(float), g.to_numpy(float)))


def level_of(d_km: float, r_core: float, margin: float) -> int:
    if d_km <= r_core:
        return 3
    if d_km <= r_core + margin:
        return 2
    if d_km <= r_core + 2 * margin:
        return 1
    return 0


def unit_risk_table(units, fc_dense, real_dense, rain, issued, r_core, margin) -> pd.DataFrame:
    rows = []
    for u in units:
        dfc = dist_to_unit_km(fc_dense["lon"], fc_dense["lat"], u)
        k = int(np.argmin(dfc))
        eta = (fc_dense["time"].iloc[k] - pd.Timestamp(issued)).total_seconds() / 3600
        d_real = float(dist_to_unit_km(real_dense["lon"], real_dense["lat"], u).min()) if len(real_dense) else np.nan
        rows.append({"unidade": u["name"], "provincia": u.get("province", ""), "d_fc_km": float(dfc[k]),
                     "d_real_km": d_real, "eta_h": eta, "eta_limite": k == len(fc_dense) - 1,
                     "chuva_mm": rain_in_unit(rain, u)})
    t = pd.DataFrame(rows)
    t["nivel"] = [level_of(d, r_core, margin) for d in t["d_fc_km"]]
    prox = np.clip(1 - t["d_fc_km"] / (r_core + 2 * margin), 0, 1)
    rmax = np.nanmax(t["chuva_mm"].to_numpy()) if t["chuva_mm"].notna().any() else 0
    rn = (t["chuva_mm"] / rmax).fillna(0) if rmax and rmax > 0 else 0 * prox
    t["indice"] = np.round(100 * (0.5 * prox + 0.5 * rn) if rmax and rmax > 0 else 100 * prox).astype(int)
    return t


def backtest(tab: pd.DataFrame, r_core: float, margin: float) -> pd.DataFrame:
    """Compara quem foi realmente atingido (trajetoria REAL) com quem foi avisado (trajetoria PREVISTA)."""
    truth = tab["d_real_km"] <= r_core
    rows = []
    for name, thr in (("Sem margem de erro", r_core), ("Com margem de erro", r_core + margin)):
        al = tab["d_fc_km"] <= thr
        rows.append({"Método": name, "Atingidos": int(truth.sum()),
                     "Avisados a tempo": int((al & truth).sum()),
                     "Falhados": int((~al & truth).sum()),
                     "Falsos alarmes": int((al & ~truth).sum())})
    return pd.DataFrame(rows)

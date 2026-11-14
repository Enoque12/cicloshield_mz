import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import alert as al
from core import data as dt
from core import model as md
from core.config import BBOX, SST_THRESHOLD

st.set_page_config(page_title="CICLOSHIELD-MZ", page_icon="🌀", layout="wide")


@st.cache_data
def load_all():
    return {
        "meta": dt.load_meta(), "sst": dt.load_sst(), "rain": dt.load_rain(),
        "track": dt.load_track(), "fc": dt.load_forecast(), "coast": dt.load_coast(),
    }


if not dt.data_ready():
    st.error("Sem dados locais. Corre `python scripts/make_demo_data.py` (demo) ou "
             "`python scripts/fetch_freddy.py` (dados reais).")
    st.stop()

D = load_all()
meta, sst, rain, track, fc, coast = (D[k] for k in ("meta", "sst", "rain", "track", "fc", "coast"))

st.title("🌀 CICLOSHIELD-MZ")
st.caption("Não vamos parar o vento. Vamos tirar-lhe a força onde ele mais mata: no erro, no atraso e na falta de preparação.")
if meta.get("demo"):
    st.warning("⚠️ **DADOS DE DEMONSTRAÇÃO (sintéticos)** — não representam o Freddy real. "
               "Corre `scripts/fetch_freddy.py` para usar dados reais.")
else:
    st.caption(f"Evento: {meta.get('event')} · Fontes: {meta.get('sources')}")

tab1, tab2, tab3 = st.tabs(["🌊 Radar & Combustível Oceânico", "🔬 Simulador “E se…”", "📲 Alerta Comunitário"])


def base_fig(title):
    fig = go.Figure()
    fig.update_layout(
        title=title, height=620, margin=dict(l=10, r=10, t=50, b=10),
        xaxis=dict(range=[BBOX["lon_min"], BBOX["lon_max"]], title="Longitude"),
        yaxis=dict(range=[BBOX["lat_min"], BBOX["lat_max"]], title="Latitude", scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", y=-0.1),
    )
    return fig


def add_coast(fig):
    if coast:
        fig.add_trace(go.Scatter(x=coast["lon"], y=coast["lat"], mode="lines", name="Costa",
                                 line=dict(color="#222", width=1), hoverinfo="skip"))


# ------------------------------------------------------------------ TAB 1
with tab1:
    c1, c2 = st.columns([3, 1])
    days = [pd.Timestamp(t) for t in sst["time"].values]
    with c2:
        layer = st.radio("Camada", ["Temperatura do mar (SST)", "Chuva acumulada"] if rain is not None
                         else ["Temperatura do mar (SST)"])
        day = st.select_slider("Dia", options=days, value=days[len(days) // 2],
                               format_func=lambda d: d.strftime("%d %b %Y"))
        show_fc = st.checkbox("Mostrar trajetória prevista", value=fc is not None, disabled=fc is None)

    sl = sst.sel(time=day, method="nearest")
    fig = base_fig(f"{layer} — {day.strftime('%d/%m/%Y')}")
    if layer.startswith("Temperatura"):
        fig.add_trace(go.Heatmap(x=sl["lon"], y=sl["lat"], z=sl.values, colorscale="YlOrRd",
                                 zmin=24, zmax=32, colorbar=dict(title="°C"), name="SST",
                                 hovertemplate="lon %{x:.1f} lat %{y:.1f}<br>%{z:.1f} °C<extra></extra>"))
        fig.add_trace(go.Contour(x=sl["lon"], y=sl["lat"], z=sl.values, showscale=False,
                                 contours=dict(start=SST_THRESHOLD, end=SST_THRESHOLD, size=1, coloring="none"),
                                 line=dict(color="black", width=2.5, dash="dot"),
                                 name=f"Isoterma {SST_THRESHOLD:.0f} °C", showlegend=True, hoverinfo="skip"))
    else:
        fig.add_trace(go.Heatmap(x=rain["lon"], y=rain["lat"], z=rain.values, colorscale="Blues",
                                 colorbar=dict(title="mm"), zmin=0, name="Chuva",
                                 hovertemplate="lon %{x:.1f} lat %{y:.1f}<br>%{z:.0f} mm<extra></extra>"))
    add_coast(fig)
    fig.add_trace(go.Scatter(x=track["lon"], y=track["lat"], mode="lines+markers", name="Trajetória real",
                             line=dict(color="black", width=3), marker=dict(size=5),
                             customdata=np.stack([track["time"].dt.strftime("%d/%m %Hh"), track["wind_kt"]], axis=-1),
                             hovertemplate="%{customdata[0]}<br>vento %{customdata[1]} kt<extra>real</extra>"))
    if fc is not None and show_fc:
        fig.add_trace(go.Scatter(x=fc["lon"], y=fc["lat"], mode="lines+markers", name="Trajetória prevista",
                                 line=dict(color="#d6001c", width=3, dash="dash"), marker=dict(symbol="x", size=8)))
    near = track.iloc[(track["time"] - (day + pd.Timedelta(hours=12))).abs().argsort()[:1]]
    fig.add_trace(go.Scatter(x=near["lon"], y=near["lat"], mode="markers", name="Posição no dia",
                             marker=dict(size=18, symbol="circle-open", line=dict(width=3, color="#0057ff"))))
    c1.plotly_chart(fig, width="stretch")

    with c2:
        frac = float((sl >= SST_THRESHOLD).mean()) * 100
        st.metric(f"Área do canal ≥ {SST_THRESHOLD:.0f} °C", f"{frac:.0f} %")
        st.metric("Vento máx. no dia", f"{int(near['wind_kt'].iloc[0])} kt · {md.category(float(near['wind_kt'].iloc[0]))}")
        if fc is not None:
            err = md.track_errors(track, fc)
            if len(err):
                st.metric("Erro médio da previsão", f"{err['err_km'].mean():.0f} km")
                st.metric("Erro máximo", f"{err['err_km'].max():.0f} km")
        else:
            st.info("Sem previsão em `data/forecast.csv`. Preenche-o (ver README) para medir o erro.")
    if fc is not None:
        with st.expander("Erro de previsão por prazo"):
            err = md.track_errors(track, fc)
            tbl = err[["valid", "lead_h", "err_km"]].rename(columns={
                "valid": "Instante", "lead_h": "Prazo (h)", "err_km": "Erro (km)"})
            tbl[["Prazo (h)", "Erro (km)"]] = tbl[["Prazo (h)", "Erro (km)"]].round(1)
            st.dataframe(tbl, hide_index=True)

# ------------------------------------------------------------------ TAB 2
with tab2:
    st.markdown("Quanto perderia o ciclone se o mar estivesse mais frio? "
                "**Modelo ilustrativo e simples — não é uma previsão operacional.**")
    peak = track.loc[track["wind_kt"].idxmax()]
    base_sst = md.local_sst(sst, peak["time"].normalize(), peak["lat"], peak["lon"])
    if not np.isfinite(base_sst):
        base_sst = 29.5
    base_sst = round(base_sst, 1)

    a, b = st.columns([1, 2])
    with a:
        st.metric("SST medida junto ao pico", f"{base_sst:.1f} °C")
        sim = st.slider("Temperatura do mar simulada (°C)", round(base_sst - 2.0, 1), base_sst, base_sst, 0.1)
        sens = st.slider("Sensibilidade (kt por °C) — hipótese", 2.0, 12.0, 6.0, 0.5,
                         help="Relação linear assumida. Valida na literatura (intensidade potencial) antes de apresentar.")
        delta = sim - base_sst
        v0 = float(peak["wind_kt"])
        v1 = md.weakened_wind(v0, delta, sens)
        st.metric("Vento máximo", f"{v1 * md.KT_TO_KMH:.0f} km/h", f"{(v1 - v0) * md.KT_TO_KMH:.0f} km/h")
        st.metric("Categoria", md.category(v1), f"antes: {md.category(v0)}", delta_color="off")
        if md.below_genesis(sim):
            st.info(f"Abaixo de {md.GENESIS_SST} °C: limiar clássico para intensificação tropical.")
    with b:
        ds_ = np.linspace(-2, 0, 41)
        ws = [md.weakened_wind(v0, d, sens) * md.KT_TO_KMH for d in ds_]
        f2 = go.Figure(go.Scatter(x=base_sst + ds_, y=ws, mode="lines", name="Vento estimado",
                                  line=dict(width=4, color="#d6001c")))
        for thr, name in md.CATEGORIES[:-1]:
            y = thr * md.KT_TO_KMH
            if min(ws) - 20 < y < max(ws) + 20:
                f2.add_hline(y=y, line_dash="dot", line_color="gray", annotation_text=name,
                             annotation_position="top left")
        f2.add_trace(go.Scatter(x=[sim], y=[v1 * md.KT_TO_KMH], mode="markers", name="Cenário",
                                marker=dict(size=16, color="#0057ff")))
        f2.update_layout(xaxis_title="Temperatura do mar (°C)", yaxis_title="Vento máximo (km/h)",
                         height=480, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(f2, width="stretch")
    st.caption("Fonte do vento de base: trajetória real do dataset. A relação SST→vento é uma hipótese linear; "
               "a investigação futura sobre arrefecimento oceânico é só uma linha de pesquisa, não uma solução.")

# ------------------------------------------------------------------ TAB 3
with tab3:
    tpl = al.load_templates()
    left, right = st.columns([1, 2])
    with left:
        nome = st.text_input("Nome do ciclone", "FREDDY")
        distrito = st.selectbox("Distrito em risco", ["Quelimane", "Nicoadala", "Mocuba", "Beira", "Vilankulo"])
        horas = st.number_input("Horas de antecedência", 6, 72, 48, 6)
        abrigo = st.text_input("Abrigo seguro (EXEMPLO — substituir por dado oficial)", "Escola Secundaria Central")
        contacto = st.text_input("Contacto de apoio (opcional)", "")
        sem_acentos = st.toggle("Remover acentos (cabe em 160 caracteres)", True)
        emit = st.button(f"🚨 Emitir Alerta {horas}h Antes", type="primary", width="stretch")
    with right:
        if emit:
            st.session_state["alerta"] = True
        if st.session_state.get("alerta"):
            st.subheader("Mensagens geradas")
            for k in ("pt", "sena", "makhuwa"):
                text_tpl = st.text_area(f"Modelo — {al.LANG_LABEL[k]}", tpl[k], key=f"tpl_{k}", height=80,
                                        help="Placeholders: {nome} {distrito} {horas} {abrigo} {contacto}")
                try:
                    msg = al.build_message(text_tpl, nome, distrito, horas, abrigo, contacto, sem_acentos)
                except (KeyError, IndexError) as e:
                    st.error(f"Placeholder inválido: {e}")
                    continue
                s = al.sms_stats(msg)
                st.code(msg, language=None)
                st.caption(f"{s['encoding']} · {s['chars']} caracteres · {s['segments']} SMS "
                           f"(limite 1 SMS = {s['limit']})")
                if k != "pt" and "POR VALIDAR" in msg:
                    st.warning(f"Tradução {al.LANG_LABEL[k]} ainda por validar com falante nativo. "
                               "Edita o modelo acima ou preenche `data/translations.json`.")
            with st.expander("Simulação USSD (sem internet)"):
                st.code(al.ussd_menu(nome, horas), language=None)
        else:
            st.info("Preenche os dados à esquerda e carrega em **Emitir Alerta**.")

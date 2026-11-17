import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import alert as al
from core import data as dt
from core import model as md
from core import risk as rk
from core.config import BBOX, SST_THRESHOLD

st.set_page_config(page_title="CICLOSHIELD-MZ", page_icon="🌀", layout="wide")


@st.cache_data
def load_all():
    return {
        "meta": dt.load_meta(), "sst": dt.load_sst(), "rain": dt.load_rain(),
        "track": dt.load_track(), "fc": dt.load_forecast(), "coast": dt.load_coast(),
        "units": dt.load_districts(),
    }


if not dt.data_ready():
    st.error("Sem dados locais. Corre `python scripts/make_demo_data.py` (demo) ou "
             "`python scripts/fetch_freddy.py` (dados reais).")
    st.stop()

D = load_all()
meta, sst, rain, track, fc, coast = (D[k] for k in ("meta", "sst", "rain", "track", "fc", "coast"))

# Cabeçalho do evento e da equipa
st.markdown("""
    <div style="text-align: center;">
        <h3>NASA Space Apps Challenge 2026</h3>
        <h2>🌍 TROPAS DO FUTURO ESPACIAL 🚀</h2>
        <h1>🌀 CICLOSHIELD-MZ</h1>
    </div>
""", unsafe_allow_html=True)

st.divider()

# Nome da solução
#st.caption(
#    "Não vamos parar o vento. Vamos tirar-lhe a força onde ele mais mata: "
#    "no erro, no atraso e na falta de preparação."
#)"""

if meta.get("demo"):
    st.warning("⚠️ **DADOS DE DEMONSTRAÇÃO (sintéticos)** - não representam o Freddy real. "
               "Corre `scripts/fetch_freddy.py` para usar dados reais.")
else:
    st.caption(f"Evento: {meta.get('event')} · Fontes: {meta.get('sources')}")

#if dt.forecast_looks_synthetic(fc):
#   st.error("🚨 A previsão em `data/forecast.csv` parece **SINTÉTICA** (demonstração). O erro por prazo, a margem e o "
#             "risco por região estão a usar números falsos. Substitui-a por avisos reais antes de apresentar.")
prov = dt.load_provenance()
rows_, headline_ = dt.data_summary(meta, sst, rain, track, fc)
st.caption(headline_)
with st.expander("🛰️ Sobre os dados: períodos, fontes e proveniência NASA"):
    st.dataframe(pd.DataFrame(rows_), hide_index=True, width="stretch")
    st.markdown("**Alinhamento no tempo.** Uma previsão emitida no instante *T* dá posições para *T+12 h … T+72 h*; "
                "comparamos cada uma com a trajetória real (IBTrACS) **no mesmo instante**. A chuva é o acumulado de todo "
                "o período (análise retrospetiva, não previsão de chuva).")
    if prov:
        st.markdown("**Verificação por APIs oficiais da NASA** (sem chave):")
        if prov.get("cmr"):
            c_ = prov["cmr"]
            st.markdown(f"- **CMR (Earthdata):** {c_['hits']} ficheiros `{c_['collection']}` para o período e a área "
                        f"(verificado em {prov['checked_at'][:10]}).")
        if prov.get("cmr_sst"):
            c2_ = prov["cmr_sst"]
            st.markdown(f"- **CMR (Earthdata):** {c2_['hits']} ficheiros `{c2_['collection']}` (temperatura do mar) para o período.")
        for e_ in (prov.get("eonet") or {}).get("events", []):
            st.markdown(f"- **EONET:** «{e_['title']}», {e_['positions']} posições, de {str(e_['first'])[:10]} a {str(e_['last'])[:10]}.")
    else:
        st.caption("Verificação NASA ainda não executada: `python scripts/nasa_api_check.py`.")

tab1, tab_risk, tab2, tab3 = st.tabs(["🌊 Radar & Combustível Oceânico", "🗺️ Risco por região",
                                      "🔬 Simulador “E se…”", "📲 Alerta Comunitário"])
RT = None   # tabela de risco (preenchida no separador de risco, usada no de alerta)


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
    fig = base_fig(f"{layer} - {day.strftime('%d/%m/%Y')}")
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

# ------------------------------------------------------------------ TAB RISCO
@st.cache_data(show_spinner="A calcular o risco por região...")
def compute_risk(_units, _fc_dense, _real_dense, _rain, key, r_core, margin):
    return rk.unit_risk_table(_units, _fc_dense, _real_dense, _rain, key[0], r_core, margin)


LV_STYLE = {3: "rgba(214,0,28,0.55)", 2: "rgba(255,140,0,0.5)", 1: "rgba(255,215,0,0.45)", 0: "rgba(190,190,190,0.15)"}

with tab_risk:
    units_d = D["units"]
    if units_d is None:
        st.info("Sem `data/districts.json`. Corre `python scripts/make_districts.py --source geoboundaries` "
                "(distritos) ou `--source naturalearth` (províncias).")
    elif fc is None:
        st.info("Preciso de `data/forecast.csv` com a trajetória prevista para calcular o risco e o alerta.")
    else:
        units = units_d["units"]
        nivel_geo = units_d["level"]
        st.markdown(f"**Alerta guiado pela margem de erro** · unidade: *{nivel_geo}* ({len(units)}). "
                    "A previsão falha em média N km a 48 h; por isso avisamos também quem está **a essa distância** "
                    "da trajetória prevista, e não só quem está debaixo dela.")
        m1, m2 = st.columns([3, 1])
        with m2:
            issued_opts = sorted(fc["issued"].unique())
            issued = st.selectbox("Aviso emitido em", issued_opts,
                                  format_func=lambda x: pd.Timestamp(x).strftime("%d/%m %Hh"))
            ref_lead = st.slider("Prazo de referência (h)", 12, 72, 48, 6)
            r_core = st.slider("Raio de impacto direto (km) - hipótese", 40, 250, 100, 10,
                               help="Distância à trajetória até onde se esperam ventos destrutivos. Valor assumido.")
            err_all = md.track_errors(track, fc)
            m_hist = rk.margin_at_lead(err_all, ref_lead)
            use_hist = st.checkbox(f"Usar margem do erro histórico ({m_hist:.0f} km)", True)
            margin = m_hist if use_hist else float(st.slider("Margem (km)", 0, 400, 100, 10))
        fc_i = fc[fc["issued"] == issued]
        fc_dense = rk.densify(fc_i, "valid")
        real_dense = rk.densify(track, "time", start=fc_dense["time"].min(), end=fc_dense["time"].max())
        RT = compute_risk(units, fc_dense, real_dense, rain, (str(issued), len(units)), r_core, float(margin))

        fig = base_fig(f"Risco por {nivel_geo} - aviso de {pd.Timestamp(issued).strftime('%d/%m %Hh')}")
        for lvl in (0, 1, 2, 3):
            xs, ys = [], []
            for u, nv in zip(units, RT["nivel"]):
                if nv == lvl:
                    for r in u["rings_np"]:
                        xs += r[:, 0].tolist() + [None]
                        ys += r[:, 1].tolist() + [None]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=LV_STYLE[lvl],
                                     line=dict(color="#555", width=0.7), name=rk.LEVEL_NAME[lvl], hoverinfo="skip"))
        add_coast(fig)
        hov = [f"<b>{r.unidade}</b><br>{rk.LEVEL_NAME[r.nivel]}<br>distância à previsão: {r.d_fc_km:.0f} km"
               f"<br>chegada: {'≥' if r.eta_limite else '~'}{r.eta_h:.0f} h"
               + (f"<br>chuva: {r.chuva_mm:.0f} mm" if pd.notna(r.chuva_mm) else "")
               + f"<br>índice: {r.indice}" for r in RT.itertuples()]
        fig.add_trace(go.Scatter(x=[u["lon"] for u in units], y=[u["lat"] for u in units], mode="markers",
                                 marker=dict(size=9, opacity=0.01), text=hov, hoverinfo="text", showlegend=False))
        lab = RT["nivel"] >= 2
        if lab.any():
            fig.add_trace(go.Scatter(x=[u["lon"] for u, k in zip(units, lab) if k],
                                     y=[u["lat"] for u, k in zip(units, lab) if k], mode="text",
                                     text=[u["name"] for u, k in zip(units, lab) if k],
                                     textfont=dict(size=11), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=fc_dense["lon"], y=fc_dense["lat"], mode="lines", name="Trajetória prevista",
                                 line=dict(color="#d6001c", width=3, dash="dash")))
        fig.add_trace(go.Scatter(x=real_dense["lon"], y=real_dense["lat"], mode="lines", name="Trajetória real",
                                 line=dict(color="black", width=3)))
        m1.plotly_chart(fig, width="stretch")

        with m2:
            st.metric("Margem usada", f"{margin:.0f} km")
            st.metric("Em alerta ou pior", int((RT["nivel"] >= 2).sum()))
            st.metric("Em vigilância", int((RT["nivel"] == 1).sum()))

        st.subheader("Funcionou? Quem foi realmente atingido vs. quem foi avisado")
        bt = rk.backtest(RT, r_core, float(margin))
        st.dataframe(bt, hide_index=True, width="stretch")
        st.caption("«Atingido» = a trajetória REAL passou a menos de R km. «Avisado» = a trajetória PREVISTA passou a "
                   "menos de R km (sem margem) ou de R + margem (com margem). "
                   "**Limite:** a margem é calibrada com o próprio ciclone onde se testa (um só caso), por isso é uma "
                   "demonstração e não uma validação. Para validar, calibra noutros ciclones (Idai, Chido) e testa no Freddy.")
        st.subheader("Regiões por nível de risco")
        show = RT.sort_values(["nivel", "indice"], ascending=[False, False]).copy()
        show["Nível"] = show["nivel"].map(rk.LEVEL_NAME)
        show["Chegada (h)"] = [("≥" if l else "") + f"{e:.0f}" for e, l in zip(show["eta_h"], show["eta_limite"])]
        st.dataframe(show[["unidade", "provincia", "Nível", "d_fc_km", "Chegada (h)", "chuva_mm", "indice"]].rename(columns={
            "unidade": "Região", "provincia": "Província", "d_fc_km": "Dist. à previsão (km)",
            "chuva_mm": "Chuva (mm)", "indice": "Índice 0-100"}).round(0), hide_index=True, width="stretch")
        st.caption("Índice 0-100 = 50% proximidade à trajetória prevista (alargada pela margem) + 50% chuva acumulada observada. "
                   "É um índice relativo de exposição, **não uma probabilidade**. "
                   "A chuva é observada a posteriori; numa situação real viria de previsão de chuva.")

# ------------------------------------------------------------------ TAB 2
with tab2:
    st.markdown("Quanto perderia o ciclone se o mar estivesse mais frio? "
                "**Modelo ilustrativo e simples - não é uma previsão operacional.**")
    peak = track.loc[track["wind_kt"].idxmax()]
    base_sst = md.local_sst(sst, peak["time"].normalize(), peak["lat"], peak["lon"])
    if not np.isfinite(base_sst):
        base_sst = 29.5
    base_sst = round(base_sst, 1)

    a, b = st.columns([1, 2])
    with a:
        st.metric("SST medida junto ao pico", f"{base_sst:.1f} °C")
        sim = st.slider("Temperatura do mar simulada (°C)", round(base_sst - 2.0, 1), base_sst, base_sst, 0.1)
        sens = st.slider("Sensibilidade (kt por °C) - hipótese", 2.0, 12.0, 6.0, 0.5,
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
    cand = None
    if RT is not None:
        cand = RT[RT["nivel"] >= 1].sort_values(["nivel", "d_fc_km"], ascending=[False, True])
        if cand.empty:
            cand = None
    with left:
        nome = st.text_input("Nome do ciclone", "FREDDY")
        if cand is not None:
            labels = {r.unidade: f"{r.unidade} - {rk.LEVEL_NAME[r.nivel]} ({'≥' if r.eta_limite else '~'}{r.eta_h:.0f} h)"
                      for r in cand.itertuples()}
            distrito = st.selectbox("Região em risco (vem do separador Risco)", list(labels), format_func=lambda k: labels[k])
            row = cand[cand["unidade"] == distrito].iloc[0]
            horas = max(int(round(row["eta_h"])), 1)
            nivel = rk.LEVEL_NAME[int(row["nivel"])].lower()
            st.caption(f"Chegada estimada: {'≥' if row['eta_limite'] else '~'}{horas} h · nível: {nivel}")
        else:
            distrito = st.selectbox("Distrito em risco (EXEMPLO)", ["Quelimane", "Nicoadala", "Mocuba", "Beira", "Vilankulo"])
            horas = int(st.number_input("Horas de antecedência", 6, 72, 48, 6))
            nivel = "alerta"
            st.caption("Sem tabela de risco: abre o separador «Risco por região» (precisa de forecast.csv).")
        abrigo = st.text_input("Abrigo seguro (EXEMPLO - substituir por dado oficial)", "Escola Secundaria Central")
        contacto = st.text_input("Contacto de apoio (opcional)", "")
        sem_acentos = st.toggle("Remover acentos (cabe em 160 caracteres)", True)
        emit = st.button(f"🚨 Emitir Alerta ({horas} h antes)", type="primary", width="stretch")
    with right:
        if emit:
            st.session_state["alerta"] = True
        if st.session_state.get("alerta"):
            st.subheader("Mensagens geradas")
            for k in ("pt", "sena", "makhuwa"):
                text_tpl = st.text_area(f"Modelo - {al.LANG_LABEL[k]}", tpl[k], key=f"tpl_{k}", height=80,
                                        help="Placeholders: {nome} {nivel} {distrito} {horas} {abrigo} {contacto}")
                try:
                    msg = al.build_message(text_tpl, nome, distrito, horas, abrigo, contacto, sem_acentos, nivel)
                except (KeyError, IndexError) as e:
                    st.error(f"Placeholder inválido: {e}")
                    continue
                s_ = al.sms_stats(msg)
                st.code(msg, language=None)
                st.caption(f"{s_['encoding']} · {s_['chars']} caracteres · {s_['segments']} SMS "
                           f"(limite 1 SMS = {s_['limit']})")
                if k != "pt" and "POR VALIDAR" in msg:
                    st.warning(f"Tradução {al.LANG_LABEL[k]} ainda por validar com falante nativo. "
                               "Edita o modelo acima ou preenche `data/translations.json`.")
            if cand is not None:
                with st.expander(f"Mensagens em português para as {len(cand)} regiões em risco"):
                    rows = []
                    for r in cand.itertuples():
                        m_ = al.build_message(tpl["pt"], nome, r.unidade, max(int(round(r.eta_h)), 1), abrigo,
                                              contacto, sem_acentos, rk.LEVEL_NAME[r.nivel].lower())
                        st_ = al.sms_stats(m_)
                        rows.append({"Região": r.unidade, "Nível": rk.LEVEL_NAME[r.nivel],
                                     "SMS": st_["segments"], "Mensagem": m_})
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            with st.expander("Simulação USSD (sem internet)"):
                st.code(al.ussd_menu(nome, horas), language=None)
        else:
            st.info("Escolhe a região à esquerda e carrega em **Emitir Alerta**.")

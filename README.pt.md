# 🌀 CycloShield-MZ

**▶ Aplicação online: https://cicloshieldmz.streamlit.app/**  ·  [English](README.md)

Protótipo de alerta antecipado de ciclones tropicais em Moçambique, feito para o **NASA Space Apps Challenge 2026**.
Caso de estudo: **Ciclone Freddy, 1 a 12 de março de 2023**.

> Não conseguimos parar um ciclone. Conseguimos reduzir o seu impacto: avisando mais cedo, avisando os sítios certos e chegando a quem só tem um telemóvel simples.

## O que faz

1. **Mostra o "combustível" do ciclone:** temperatura do mar (com a linha de 28 °C) e chuva acumulada no Canal de Moçambique.
2. **Mede o erro da previsão:** compara a trajetória prevista com a real e dá o erro em km, por prazo.
3. **Transforma esse erro numa margem de segurança:** cada distrito fica em *impacto direto*, *alerta* ou *vigilância*, pelo raio de danos mais o erro típico da previsão. Quem está na borda de uma trajetória incerta não fica de fora.
4. **Entrega o aviso:** gera SMS curtos e um menu USSD simulado para telemóveis simples, com o nível de risco e a hora estimada de chegada.

## Como usar a app (4 separadores)

| Separador | O que se vê |
|---|---|
| **Radar & Combustível Oceânico** | Mapa da temperatura do mar, linha de 28 °C, chuva, trajetória real (preto) vs prevista (vermelho tracejado), tabela do erro por prazo. |
| **Risco por região** | Mapa por distrito colorido por nível (vermelho = impacto direto, laranja = alerta, amarelo = vigilância). Raio e margem ajustáveis. Um **backtest** compara os distritos realmente atingidos com os avisados, com e sem margem. |
| **Simulador "E se…"** | Efeito ilustrativo de um mar mais frio no vento máximo. Usa uma hipótese linear editável. Não é previsão. |
| **Alerta Comunitário** | SMS por região (português; modelos em Sena e Makhuwa por validar com falantes nativos), contador de caracteres, menu USSD simulado. |

O painel **«Sobre os dados»**, no topo da app, mostra os períodos, as fontes e a origem (NASA / NOAA) de cada dado na versão publicada.

## Dados e período

Tudo cobre **1 a 12 de março de 2023**: a reintensificação do Freddy no Canal de Moçambique e o segundo toque em terra perto de Quelimane, a 11 de março.

| Dado | Fonte | Origem |
|---|---|---|
| Trajetória real e vento | IBTrACS v04r01 | NOAA |
| Chuva (acumulada) | GPM IMERG Final, 0,1° | **NASA** |
| Temperatura do mar | OISST v2.1, 0,25° | NOAA |
| Trajetória prevista | Avisos públicos, introduzidos à mão (horas de emissão na app) | Agência emissora |
| Limites dos distritos | geoBoundaries | Dados abertos |

**Como a previsão se alinha com as observações:** um aviso emitido no instante *T* dá posições para *T+12 h … T+72 h*. Cada uma é comparada com a trajetória real **no mesmo instante**. A chuva é o total acumulado de todo o período (análise retrospetiva, não previsão de chuva).

## Dados e APIs da NASA

| Componente NASA | API | Precisa de chave? |
|---|---|---|
| Encontrar ficheiros GPM IMERG (CMR, Earthdata) | `cmr.earthdata.nasa.gov/search/granules.json` | **Não** |
| Registo do evento Freddy (EONET v3) | `eonet.gsfc.nasa.gov/api/v3/events` | **Não** |
| Descarregar ficheiros GPM IMERG | NASA Earthdata (GES DISC) | **Sim**: conta gratuita Earthdata Login (token ou utilizador/palavra-passe) |

Pedidos numa linha:

```bash
# EONET: evento Freddy (sem chave)
curl "https://eonet.gsfc.nasa.gov/api/v3/events?category=severeStorms&status=all&start=2023-02-01&end=2023-03-31"

# CMR: n.º de ficheiros GPM IMERG de meia hora, 1-12 mar 2023, sobre o Canal (sem chave)
curl -sI "https://cmr.earthdata.nasa.gov/search/granules.json?short_name=GPM_3IMERGHH&version=07&temporal=2023-03-01T00:00:00Z,2023-03-12T23:59:59Z&bounding_box=30,-25,50,-10&page_size=1" | grep -i cmr-hits

# Descarregar um ficheiro (precisa do teu token Earthdata, gratuito)
curl -L -H "Authorization: Bearer $EARTHDATA_TOKEN" -O "<URL do granulo, vindo do CMR>"
```

```python
# Python: via oficial NASA usada por scripts/fetch_freddy.py quando há credenciais
import earthaccess                       # EARTHDATA_USERNAME / EARTHDATA_PASSWORD
earthaccess.login(strategy="environment")
granulos = earthaccess.search_data(short_name="GPM_3IMERGDF", version="07",
                                   temporal=("2023-03-01", "2023-03-12"), bounding_box=(30, -25, 50, -10))
```

- O `scripts/fetch_freddy.py` usa **primeiro a via oficial da NASA** quando há credenciais Earthdata e, se não houver, recorre a um espelho Zarr público dos mesmos dados GPM IMERG.
- `python scripts/nasa_api_check.py` chama o CMR e o EONET (sem chave) e guarda o resultado em `data/nasa_provenance.json`. A app **mostra-o no painel «Sobre os dados»** e continua totalmente offline.
- **Nota honesta:** a temperatura do mar vem do NOAA OISST, não da NASA. O produto NASA MUR exige login Earthdata e o servidor não era acessível a partir da nossa rede. Trocar é possível com `--sst-source mur`.

## O que podemos e não podemos afirmar

- É uma **demonstração num evento real**, não um sistema de previsão validado.
- A margem de erro é calibrada e testada no mesmo ciclone (Freddy). Validar seria calibrar com Idai/Chido e testar no Freddy.
- O índice de exposição é relativo, **não é uma probabilidade**. O simulador é ilustrativo.
- O USSD é **simulado**. Um serviço real exige código curto, acordos com operadoras e com o regulador (INCM) e mandato institucional (INGD/INAM). O USSD é um canal de consulta; o aviso seria por SMS ou *cell broadcast*.
- As mensagens em línguas locais são modelos até serem validadas por falantes nativos.

## Estado

**Feito:** app de quatro separadores que funciona offline; trajetória, chuva e temperatura do mar reais do Freddy; medição do erro da previsão; níveis de risco por distrito com margem e backtest; gerador de SMS e USSD simulado; verificação de proveniência NASA.
**Em curso:** mensagens validadas em Sena/Makhuwa; abrigos e rotas oficiais.
**Seguinte:** Ndau e rádio comunitária; rotas de evacuação; validação com Idai/Chido; piloto de USSD real com INGD/INAM e uma operadora; temperatura do mar NASA MUR.

## Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Dados reais (uma vez, com internet): `pip install -r requirements-fetch.txt`, depois `python scripts/fetch_freddy.py` e `python scripts/make_districts.py --source geoboundaries`. A app só lê ficheiros locais em `data/`, por isso funciona offline. Se aparecer o aviso amarelo de "dados de demonstração", os dados são sintéticos.

## Repositório

```
app.py                 app Streamlit
core/                  dados, modelo de risco, alertas, reparação de texto
scripts/               fetch_freddy.py, nasa_api_check.py, make_districts.py, ...
data/                  cache local (vai no commit)
docs/                  notas da equipa e README anterior
```

## Créditos

Equipa: 🌍 TROPAS DO FUTURO ESPACIAL 🚀 · Matola / Maputo, Moçambique.
Dados: NASA GPM IMERG, NOAA IBTrACS, NOAA OISST, geoBoundaries, Natural Earth.

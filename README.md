# 🌀 CICLOSHIELD-MZ

Protótipo desenvolvido para o **NASA Space Apps Challenge 2026**.
Estudo de caso: **Ciclone Freddy (março de 2023)**, costa da Zambézia, Moçambique.

> Não vamos parar o vento. Vamos tirar-lhe a força onde ele mais mata: no erro de previsão, no atraso do alerta e na falta de preparação.

---

## 1. Tema do projeto

**Enfraquecer o impacto dos ciclones em Moçambique: correção do erro de previsão e alerta antecipado com dados abertos da NASA.**

Moçambique é um dos países mais expostos do mundo a ciclones tropicais (Idai 2019, Freddy 2023, Chido 2024). Não é possível enfraquecer fisicamente um ciclone já formado; é possível **reduzir o seu impacto** avisando melhor e mais cedo.

## 2. Propósito

Mostrar, com dados abertos e um caso real, que:

1. **O "combustível" do ciclone é observável**: mar acima de 28 °C e chuva acumulada no Canal de Moçambique.
2. **A previsão tem erro mensurável**: comparamos a trajetória prevista com a real e medimos o erro em km, por prazo.
3. **O erro pode ser usado em favor das pessoas**: em vez de avisar só quem está debaixo da trajetória prevista, avisamos também quem está dentro da **margem de erro histórica** (alerta guiado pela margem de erro).
4. **O aviso tem de chegar**: geramos mensagens curtas para telemóveis básicos (SMS/USSD), com a região, o nível de risco e a hora estimada de chegada.

**Diferencial:** a ligação entre dados e a "última milha" (mensagem curta, sem internet), com o erro de previsão tratado de forma explícita e testável.

---

## 3. Como correr

```bash
pip install -r requirements.txt
streamlit run app.py
```

A app lê **apenas ficheiros locais** em `data/` (nunca faz chamadas de rede), por isso funciona sem internet na apresentação.
Se `data/meta.json` disser `"demo": true`, a app mostra um aviso amarelo: os dados são **sintéticos** e não representam o Freddy.

### Obter dados reais (uma vez, com internet)

```bash
pip install -r requirements-fetch.txt
python scripts/fetch_freddy.py            # trajetória + temperatura do mar + chuva
python scripts/make_districts.py --source geoboundaries   # limites dos distritos
```

### Trajetória prevista (manual, ver secção 8)

Preencher `data/forecast.csv`.

---

## 4. Navegação na app

A app tem 4 separadores.

### 🌊 Radar & Combustível Oceânico
Mostra **o que alimentou o ciclone e por onde ele passou**.

| Elemento | O que representa |
|---|---|
| Camada *Temperatura do mar (SST)* | Temperatura da superfície do mar, por dia (escala amarelo→vermelho). |
| Linha pontilhada a preto | **Isoterma de 28 °C**: dentro dela o mar é quente o suficiente para alimentar o ciclone. |
| Camada *Chuva acumulada* | Chuva total (mm) no período, GPM IMERG. |
| Linha preta contínua | **Trajetória real** (IBTrACS). Ao passar o rato, mostra data/hora e vento (nós). |
| Linha vermelha tracejada | **Trajetória prevista** (de `forecast.csv`). |
| Círculo azul | Posição do ciclone no dia escolhido no seletor. |
| *Área do canal ≥ 28 °C* | Percentagem do mapa com mar acima de 28 °C nesse dia. |
| *Vento máx. no dia* | Vento máximo do ciclone (nós) e a categoria Saffir-Simpson. |
| *Erro médio / máximo da previsão* | Média e maior distância (km) entre posição prevista e real. |
| Tabela **Erro de previsão por prazo** | Cada linha é um palpite da previsão. **Instante** = momento previsto; **Prazo (h)** = quantas horas antes o palpite foi feito; **Erro (km)** = distância entre o previsto e o real nesse instante. Normalmente o erro cresce com o prazo. |

### 🗺️ Risco por região
Transforma a previsão e o seu erro em **níveis de alerta por distrito** (ou província, se só houver províncias).

| Elemento | O que representa |
|---|---|
| Cores do mapa | **Vermelho** impacto direto · **laranja** alerta · **amarelo** vigilância · cinzento sem alerta. |
| Raio de impacto direto (R) | Distância à trajetória até onde se esperam ventos destrutivos. **Hipótese editável** (100 km por defeito). |
| Margem | Erro típico da previsão ao prazo escolhido (vem da tabela do separador 1). Pode ser substituída manualmente. |
| Regra dos níveis | Distância à trajetória prevista ≤ R → impacto direto; ≤ R + margem → alerta; ≤ R + 2×margem → vigilância. |
| Chegada (h) | Hora estimada de chegada a partir do aviso. «≥» significa que a previsão acaba antes de lá chegar (limite do horizonte). |
| Tabela *Quem foi atingido vs. quem foi avisado* | **Backtest**: compara regiões realmente atingidas (trajetória real a menos de R km) com as avisadas (trajetória prevista), **com e sem margem de erro**. |
| Índice 0-100 | 50% proximidade à trajetória prevista (alargada pela margem) + 50% chuva observada. É um **índice relativo de exposição, não uma probabilidade**. |

### 🔬 Simulador "E se…"
Mostra, de forma **ilustrativa**, quanto vento o ciclone perderia com mar mais frio.

- *SST medida junto ao pico*: temperatura do mar perto do ponto de maior intensidade.
- *Temperatura simulada* (slider): desce até 2 °C.
- *Sensibilidade (kt por °C)*: **hipótese** linear editável (6 por defeito). Não é um modelo físico validado.
- Gráfico: vento estimado (km/h) vs. temperatura, com as categorias; o ponto azul é o cenário escolhido.

### 📲 Alerta Comunitário
Gera o aviso para telemóveis básicos.

- A região e a hora de chegada vêm do separador de risco (as regiões em vigilância ou pior).
- Mensagens em Português, Sena e Makhuwa (modelos editáveis; **Sena e Makhuwa ainda por validar**).
- Contador de caracteres e de SMS: com acentos a mensagem passa de 160 para 70 caracteres por SMS; o botão *Remover acentos* mantém-na em 1 SMS.
- Tabela com a mensagem em português para todas as regiões em risco.
- Simulação de menu USSD (sem internet).

---

## 5. Fontes de dados

| Dado | Fonte | Observação |
|---|---|---|
| Trajetória real e vento | IBTrACS v04r01 (NOAA/NCEI) | Ventos de agências diferentes têm períodos de média diferentes (10 min vs 1 min). |
| Temperatura do mar | NOAA OISST v2.1 (AVHRR), 0,25° | **É NOAA, não NASA.** O MUR (NASA) exige conta Earthdata (melhoria futura). |
| Chuva | GPM IMERG Final (NASA), via Zarr público do Source Cooperative | Repositório de terceiros com dados NASA; confirmar cobertura antes de usar noutros períodos. |
| Costa | Natural Earth 50m | Embutida offline. |
| Limites administrativos | geoBoundaries (distritos) / Natural Earth (províncias) | `scripts/make_districts.py`. |
| Trajetória prevista | Avisos públicos (JTWC), preenchidos à mão | Ver secção 8. |

---

## 6. Tecnologias usadas e porquê

| Tecnologia | Para que serve aqui | Porquê esta escolha |
|---|---|---|
| **Python** | Dados, modelo, risco e alertas | Uma só linguagem para tudo, com o ecossistema científico (dados NASA/NOAA) à mão. |
| **Streamlit** | Interface web (4 separadores) | Permite um protótipo interativo em horas, sem *build* de front-end, e tem deploy gratuito. **Trade-off:** menos personalização visual do que React. Como a lógica está em `core/` sem depender do Streamlit, pode migrar-se depois para FastAPI + React sem reescrever as regras. |
| **Plotly** | Mapas e gráficos | Os mapas são desenhados em eixos longitude/latitude, **sem mapas de fundo da internet**, por isso funcionam offline. Mapas com *tiles* (ex.: Folium) falhariam sem rede na apresentação. |
| **pandas / NumPy** | Tabelas e cálculo | Cálculo vetorizado de distâncias a polígonos, interpolação de trajetórias e erros. |
| **xarray + netCDF4** | Grelhas de temperatura do mar e chuva | NetCDF é o formato nativo dos dados NASA/NOAA; o xarray corta por região e tempo e mantém as coordenadas. |
| **Zarr + s3fs** | Ler a chuva GPM IMERG | O conjunto global é enorme (dezenas de TB); o Zarr lê **só o recorte** necessário, sem descarregar tudo e sem conta. |
| **requests** | Download da trajetória (IBTrACS) | Simples e suficiente. |
| **earthaccess** (opcional) | Acesso NASA Earthdata (MUR, GPM oficial) | Exige conta gratuita; ficou **opcional** para não bloquear o projeto. |
| **CSV / NetCDF / JSON locais** | Cache em `data/` | A app **nunca faz chamadas de rede**: a demonstração não falha por causa da internet. |
| **Natural Earth / geoBoundaries** | Costa e limites administrativos | Dados abertos, simplificados (algoritmo Douglas-Peucker) para ficheiros pequenos e rápidos. |
| **Cálculo geométrico próprio** (haversine, ponto-em-polígono) | Distância da trajetória a cada região | Evita dependências pesadas (GeoPandas/Shapely) no deploy. **Trade-off:** usa uma projeção equirretangular aproximada e é menos robusto do que bibliotecas dedicadas. |
| **Git/GitHub + Streamlit Community Cloud** | Partilha com a equipa e demo online | Gratuito e simples. Serve também de cópia de segurança da demonstração. |

**Escolhas de dados feitas por necessidade (e porquê):** a temperatura do mar vem do NOAA OISST (S3 público, sem conta) porque o servidor do MUR/ERDDAP não era acessível a partir da nossa rede; a chuva GPM vem de um Zarr público porque a coleção do Planetary Computer termina em 2021 e não cobre 2023.

## 7. Estado do projeto

### ✅ Concluído
- Estrutura da app em 4 separadores, funcional e offline (dados em cache local).
- Download de trajetória real (IBTrACS), temperatura do mar (OISST via S3) e chuva (GPM IMERG via Zarr).
- Mapa do Canal de Moçambique: temperatura do mar, isoterma de 28 °C, chuva acumulada, trajetória real, posição por dia.
- Cálculo do erro de previsão por prazo (km) e margem de erro por prazo.
- **Risco por região**: níveis de alerta, índice de exposição, hora de chegada estimada e backtest com/sem margem.
- Limites de distritos (geoBoundaries) e costa offline.
- Simulador ilustrativo de sensibilidade à temperatura do mar.
- Gerador de alerta SMS com contador de caracteres, menu USSD simulado e mensagens por região.

### 🟡 Por completar (dependências já identificadas)
- **`data/forecast.csv`** com a trajetória prevista. **Sem ele, o erro por prazo, o mapa de risco e o alerta ligado ao risco não funcionam.**
- Tradução **Sena** e **Makhuwa** validada por falante nativo (hoje há marcadores "POR VALIDAR").
- Abrigos seguros oficiais (hoje é um campo de texto com exemplo).
- Rever e fixar o raio de impacto (R) e a sensibilidade do simulador com base em literatura.

### ⬜ Por integrar (fora do que foi feito até agora)
- **Língua Ndau** e rádio comunitária como canal de alerta.
- **Rota de evacuação segura** (evitar pontes e estradas que inundam).
- Dados NASA adicionais (CYGNSS, AIRS, SMAP) e deteção antecipada da formação do ciclone.
- **Validação do método** com mais ciclones (Idai, Chido): calibrar a margem em uns e testar noutros. Hoje a margem é calibrada e testada no mesmo caso (Freddy).
- **Probabilidade** de toque em terra (hoje usamos níveis e um índice, não probabilidades).
- Segunda fonte independente (Meteomatics) para validação cruzada.
- Vídeo de demonstração de 30 s.
- Versão otimizada para telemóvel.

### Como isto se relaciona com os objetivos da proposta

| Objetivo original | Estado |
|---|---|
| 1. Detetar a formação antes dos modelos atuais | **Não cumprido.** Reformulado: monitorizar o combustível oceânico (mar ≥ 28 °C) e a chuva. |
| 2. Corrigir o erro de previsão | **Reformulado:** medir o erro histórico e usá-lo como margem de alerta (não é um modelo de correção treinado). |
| 3. Simular o enfraquecimento | Parcial: simulador ilustrativo, com hipóteses explícitas. |
| 4. Avisar por SMS/USSD/rádio, em línguas locais | Parcial: SMS e USSD simulados; falta validação de línguas, rádio, Ndau e rota segura. |
| 5. Mapa interativo por distrito | Cumprido para risco por distrito (com distritos descarregados); falta otimização para telemóvel. |

---

## 8. Como preencher `data/forecast.csv`

Formato (uma linha por posição prevista):

```csv
issued,valid,lat,lon,wind_kt
2023-03-08 00:00,2023-03-08 12:00,-18.5,38.2,80
2023-03-08 00:00,2023-03-09 00:00,-18.0,37.6,75
```

- `issued`: hora (UTC) em que o aviso foi emitido. `valid`: hora (UTC) a que a posição se refere.
- Latitude **sul negativa**, longitude **leste positiva**. `wind_kt` é opcional (não entra nos cálculos).
- Usar 2 a 3 avisos (por exemplo 8, 9 e 10 de março de 2023), com as posições a +12, +24, +36, +48 e +72 h.
- Indicar sempre a fonte do aviso na apresentação (o erro medido é o dessa agência).

---

## 9. Recomendações da equipa técnica

**Engenharia**
- **Offline primeiro:** a app só lê `data/`. Fazer commit dos dados e levar uma cópia local para a apresentação.
- **Congelar funcionalidades** nas últimas horas: só correção de erros, nada novo.
- Manter a lógica em `core/`, separada da interface, para poder migrar para React/FastAPI depois.
- Testar a app num telemóvel e em modo avião antes de apresentar.
- Limitar o tempo gasto em fontes de dados problemáticas (ex.: chuva é o enfeite do mapa; o núcleo é mar quente + trajetória + erro).

**Ciência e honestidade**
- **Não inventar números.** Retirar da proposta o exemplo "68% de probabilidade em 36 h" e "detetaria 24 h antes", ou só os manter se existir um backtest que os suporte.
- **Dizer a fonte exata:** temperatura do mar = NOAA (não NASA); chuva = NASA GPM; previsão = a agência do aviso (ex.: JTWC).
- A margem é calibrada e testada no mesmo ciclone: apresentar como **demonstração**, e como próximo passo validar com Idai e Chido.
- O simulador "E se…" é ilustrativo (relação linear assumida). Não o apresentar como previsão.
- Moderar afirmações como "não existe nenhum sistema nacional" e "dependência de uma única fonte": **verificar primeiro** o que o INAM e o INGD já fazem e usar "complementa".
- Confirmar a fonte de números citados na proposta (ex.: "48 h reduzem mortes em até 70%").

**Mensagens de alerta**
- **Não usar tradução automática** em Sena, Makhuwa ou Ndau: validar com falante nativo (mesmo por WhatsApp).
- Substituir os abrigos de exemplo por dados oficiais, ou dizer claramente que são ilustrativos.
- Manter as mensagens em 1 SMS (remover acentos) e mostrar o contador.


---

## 10. O que pode impactar a plateia

- **Começar pela pessoa, não pela tecnologia.** Freddy, a costa de Quelimane, uma família que precisa de saber para onde ir. A tecnologia explica como esse aviso chega.
- **Mostrar a ideia central num gesto:** na aba de risco, mudar a margem de erro e ver as regiões a mudar de cor. É a ideia ("avisar também quem a previsão pode falhar") em dois segundos.
- **Um número real e verificável:** o quadro *quem foi atingido vs. quem foi avisado*, com e sem margem. Só usá-lo depois de ter dados reais, e dizer sempre as suas limitações.
- **A última milha:** mostrar o SMS num telemóvel básico (ou num ecrã de telemóvel) com a região, o nível e a hora de chegada, e o contador de caracteres.
- **Funcionar offline:** apresentar com o computador em modo avião. É prova de robustez para um país onde a eletricidade e a internet falham quando mais são precisas.
- **Línguas locais validadas:** se houver um falante nativo (presente ou em vídeo curto), a credibilidade aumenta muito.
- **Honestidade como ponto forte:** apresentar os limites e as fontes antes de o júri os descobrir. Mostra rigor científico.
- **Visão futura, assinalada como futura:** replicação para Madagáscar, Malawi, Zimbabué e Comores; mais ciclones; mais dados NASA.
- **Evitar:** promessas absolutas ("salva vidas"), números não medidos e jargão sem explicação.

**Roteiro sugerido para o vídeo de 30 s**

| Tempo | Conteúdo |
|---|---|
| 0-5 s | O problema: Freddy, Quelimane, o aviso que chega tarde ou com erro. |
| 5-12 s | O mar quente (≥ 28 °C) e a trajetória prevista vs. real. |
| 12-22 s | O mapa de risco: a margem de erro alarga o alerta. |
| 22-30 s | O SMS num telemóvel simples e a frase final. |

---

## 11. Limites e honestidade científica

- O **simulador** usa uma relação linear assumida entre temperatura do mar e vento. É ilustrativo, não operacional.
- O **raio de impacto** e a **margem** são parâmetros; a margem é calibrada com o mesmo caso onde é testada (um só ciclone). Os resultados são uma **demonstração**, não uma validação.
- O **índice** de exposição não é uma probabilidade. A chuva usada é observada a posteriori.
- Abrigos e textos em línguas locais são exemplos até serem validados com fontes oficiais e falantes nativos.
- A temperatura do mar vem da NOAA; a chuva (GPM) é da NASA.

---

## 12. Estrutura do repositório

```
app.py                     interface Streamlit (4 separadores)
core/
  config.py                caixa geográfica, limiares, caminhos
  data.py                  leitura de dados locais
  model.py                 categorias, simulador, erro de previsão
  risk.py                  níveis por região, índice, backtest
  alert.py                 mensagens SMS/USSD, contador de caracteres
scripts/
  fetch_freddy.py          descarrega trajetória, mar e chuva (uma vez)
  make_districts.py        gera data/districts.json
  make_coast.py            gera a costa offline
  make_demo_data.py        dados sintéticos de demonstração
data/                      cache local (commit no git, exceto data/raw/)
requirements.txt           para correr a app / deploy
requirements-fetch.txt     para os scripts de download
```

## 13. Equipa

🌍 TROPAS DO FUTURO ESPACIAL 🚀 · Maputo, Moçambique · NASA Space Apps Challenge 2026

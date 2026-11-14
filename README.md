# CICLOSHIELD-MZ (MVP, NASA Space Apps 2026)

App Streamlit com 3 separadores sobre o Ciclone Freddy (2023). A app lê só ficheiros locais em `data/`, por isso funciona sem internet.

## Arranque
```bash
pip install -r requirements.txt
python scripts/make_demo_data.py     # dados SINTETICOS (ja vem gerado) -> a app corre ja
streamlit run app.py
```

## Passar para dados reais (com internet, uma vez)
```bash
# opcional, so para a chuva GPM IMERG (conta gratuita Earthdata):
export EARTHDATA_USERNAME=... EARTHDATA_PASSWORD=...
python scripts/fetch_freddy.py
```
- Trajetória real: IBTrACS (NOAA). SST: GHRSST MUR (NASA JPL) via ERDDAP. Chuva: GPM IMERG (opcional).
- `fetch_freddy.py` **não foi testado contra os servidores reais** (o ambiente onde foi escrito não tinha acesso). Cada fonte é independente; se uma falhar, a mensagem diz qual.
- Faz commit de `data/` no git e leva uma cópia no pen drive para a apresentação.

## Trajetória prevista (a parte difícil)
Preenche `data/forecast.csv` à mão com posições previstas de avisos públicos (Météo-France La Réunion / JTWC):
```
issued,valid,lat,lon,wind_kt
2023-03-08 00:00,2023-03-08 12:00,-18.5,38.2,80
```
Indica sempre a fonte do aviso na apresentação.

## Traduções (Sena / Makhuwa)
Não há tradução automática. Peça a um falante nativo para escrever os modelos em `data/translations.json`:
```json
{"sena": "...{distrito}...{horas}h...{abrigo}...", "makhuwa": "..."}
```
Placeholders: `{nome} {distrito} {horas} {abrigo} {contacto}`. Também podem ser editados na própria app.

## Estrutura
- `app.py`: interface (3 separadores)
- `core/`: dados, modelo, alertas (sem Streamlit, reutilizável por FastAPI/React)
- `scripts/`: download de dados, geração de demo, costa offline
- `data/`: cache local (a costa vem do Natural Earth 50m)

## Limites honestos
- O simulador "E se..." usa uma relação linear SST→vento com sensibilidade configurável. É ilustrativo, não operacional.
- Os abrigos e distritos da aba 3 são exemplos, não dados oficiais.

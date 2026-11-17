# 🌀 CycloShield-MZ

**▶ Live app: https://cicloshieldmz.streamlit.app/**  ·  [Português](README.pt.md)

Early-warning prototype for tropical cyclones in Mozambique, built for the **NASA Space Apps Challenge 2026**.
Case study: **Cyclone Freddy, 1–12 March 2023**.

> We cannot stop a cyclone. We can reduce its impact: by warning earlier, warning the right places, and reaching people who only have a basic phone.

## What it does

1. **Shows the cyclone's "fuel":** sea surface temperature (with the 28 °C isotherm) and accumulated rainfall in the Mozambique Channel.
2. **Measures forecast error:** compares the predicted track with the real one and reports the error in km by lead time.
3. **Turns that error into a safety margin:** each district is classified as *direct impact*, *alert* or *watch*, using the damage radius plus the typical forecast error. Districts near the edge of an uncertain path are not left out.
4. **Delivers the warning:** generates short SMS messages and a simulated USSD menu for basic phones, with risk level and estimated arrival time.

## Using the app (4 tabs)

| Tab | What you see |
|---|---|
| **Radar & Ocean Fuel** | Sea temperature map, 28 °C line, rainfall layer, real track (black) vs predicted track (red dashed), forecast error table by lead time. |
| **Risk by Region** | District map coloured by level (red = direct impact, orange = alert, yellow = watch). Adjustable damage radius and error margin. A **backtest** compares districts actually hit with districts warned, with and without the margin. |
| **What-if Simulator** | Illustrative effect of cooler seas on maximum wind. Uses an explicit, editable linear assumption. Not a forecast. |
| **Community Alert** | SMS text per region (Portuguese; Sena and Makhuwa templates pending native-speaker validation), character counter, simulated USSD menu. |

The **"About the data"** panel at the top of the app lists the exact periods, sources and origin (NASA / NOAA) of every dataset in the deployed version.

## Data and time coverage

Everything covers **1–12 March 2023**: Freddy's re-intensification in the Mozambique Channel and its second landfall near Quelimane on 11 March.

| Data | Source | Origin |
|---|---|---|
| Real track and wind | IBTrACS v04r01 | NOAA |
| Rainfall (accumulated) | GPM IMERG Final, daily, V07, 0.1° | **NASA** |
| Sea surface temperature | GHRSST MUR L4 v4.2 (MUR25), daily, 0.25° | **NASA** |
| Predicted track | Public cyclone advisories, entered manually (issue times shown in the app) | Issuing agency |
| District boundaries | geoBoundaries | Open data |

**How forecast and observations line up:** an advisory issued at time *T* gives positions for *T+12 h … T+72 h*. Each is compared with the real track at the **same instant**. Rainfall is the accumulated total for the whole period (a retrospective analysis, not a rainfall forecast).

## NASA data and API integration

| NASA component | API | Key needed? |
|---|---|---|
| Find GPM IMERG files (CMR, Earthdata) | `cmr.earthdata.nasa.gov/search/granules.json` | **No** |
| Natural-event record for Freddy (EONET v3) | `eonet.gsfc.nasa.gov/api/v3/events` | **No** |
| Download GPM IMERG files | NASA Earthdata (GES DISC) | **Yes**: free Earthdata Login account (token or username/password) |

One-line requests:

```bash
# EONET: Freddy event (no key)
curl "https://eonet.gsfc.nasa.gov/api/v3/events?category=severeStorms&status=all&start=2023-02-01&end=2023-03-31"

# CMR: number of GPM IMERG daily files for 1-12 Mar 2023 over the Channel (no key; expect 12)
curl -sI "https://cmr.earthdata.nasa.gov/search/granules.json?short_name=GPM_3IMERGDF&version=07&temporal=2023-03-01T00:00:00Z,2023-03-12T23:59:59Z&bounding_box=30,-25,50,-10&page_size=1" | grep -i cmr-hits

# Download a file (needs your free Earthdata token)
curl -L -H "Authorization: Bearer $EARTHDATA_TOKEN" -O "<granule URL from CMR>"
```

```python
# Python: official NASA route used by scripts/fetch_freddy.py when credentials are set
import earthaccess                       # EARTHDATA_USERNAME / EARTHDATA_PASSWORD
earthaccess.login(strategy="environment")
granules = earthaccess.search_data(short_name="GPM_3IMERGDF", version="07",
                                   temporal=("2023-03-01", "2023-03-12"), bounding_box=(30, -25, 50, -10))
```

- `scripts/fetch_freddy.py` downloads rainfall (GPM IMERG) and sea surface temperature (MUR) through the **official NASA route** (Earthdata). If rainfall fails, it can fall back to a public Zarr mirror, which the script rejects when it is empty.
- `python scripts/nasa_api_check.py` calls CMR and EONET (no key) and saves the result to `data/nasa_provenance.json`. The app **displays it in the "About the data" panel** and stays fully offline.
- **What is not NASA:** the cyclone track and wind (IBTrACS) come from NOAA. Rainfall and sea surface temperature are NASA products, downloaded with a free Earthdata login (`python scripts/fetch_freddy.py --sst-source mur-nasa`). NOAA OISST remains available as a fallback (`--sst-source oisst`).

## What we can and cannot claim

- It is a **demonstration on one real event**, not a validated forecasting system.
- The error margin is calibrated and tested on the same cyclone (Freddy). Validation would calibrate on Idai/Chido and test on Freddy.
- The exposure index is relative, **not a probability**. The what-if simulator is illustrative.
- USSD is **simulated**. A real service needs a short code, mobile-operator and regulator (INCM) agreements, and an institutional mandate (INGD/INAM). USSD is a pull channel, so SMS or cell broadcast would carry the alert.
- Local-language messages are templates until validated by native speakers.

## Status

**Done:** four-tab app that works offline; real track, rainfall and sea temperature for Freddy; forecast-error measurement; district risk levels with margin and backtest; SMS generator and simulated USSD; NASA provenance check.
**In progress:** validated Sena/Makhuwa messages; official shelters and routes.
**Next:** Ndau and community radio; evacuation routes; Idai/Chido validation; real USSD pilot with INGD/INAM and an operator.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Real data (once, with internet): `pip install -r requirements-fetch.txt`, then `python scripts/fetch_freddy.py --sst-source mur-nasa` and `python scripts/make_districts.py --source geoboundaries`. The app reads only local files in `data/`, so it works offline. If the yellow "demo data" banner appears, the data are synthetic.

**Credentials:** copy `.env.example` to `.env` and fill in your free Earthdata login (it is git-ignored). Only the download scripts need it; the deployed app does not.

## Repository

```
app.py                 Streamlit app
core/                  data loading, risk model, alerts, text repair
scripts/               fetch_freddy.py, nasa_api_check.py, make_districts.py, ...
data/                  local cache (committed)
docs/                  team notes and previous README
```

## Credits

Team: 🌍 TROPAS DO FUTURO ESPACIAL 🚀 · Maputo, Mozambique.
Data: NASA GPM IMERG, NASA GHRSST MUR, NOAA IBTrACS, geoBoundaries, Natural Earth.

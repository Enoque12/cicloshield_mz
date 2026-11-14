from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"

# Canal de Mocambique
BBOX = {"lon_min": 30.0, "lon_max": 50.0, "lat_min": -25.0, "lat_max": -10.0}

# Janela do Freddy: re-intensificacao no Canal e 2.o toque em terra (Zambezia)
START, END = "2023-03-01", "2023-03-12"

SST_THRESHOLD = 28.0      # "combustivel" destacado no mapa
GENESIS_SST = 26.5        # limiar classico para intensificacao tropical

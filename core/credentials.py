"""Credenciais Earthdata, sem as pôr no código.

Ordem de procura (a primeira que existir ganha):
  1. variaveis de ambiente (ex.: $env:EARTHDATA_USERNAME no PowerShell)
  2. ficheiro .env na raiz do projeto (python-dotenv)
  3. Streamlit secrets (.streamlit/secrets.toml ou painel Secrets do Streamlit Cloud)
So os scripts de download (fetch_freddy.py) precisam disto. A app publicada NAO precisa.
"""
import os

from .config import ROOT

NAMES = ("EARTHDATA_USERNAME", "EARTHDATA_PASSWORD")


def load_credentials() -> bool:
    """Garante EARTHDATA_USERNAME/PASSWORD em os.environ. Devolve True se ambas existirem."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)   # nunca sobrepoe o que ja esta no ambiente
    except ImportError:
        pass
    for name in NAMES:
        if not os.getenv(name):
            try:
                import streamlit as st
                val = st.secrets.get(name)
                if val:
                    os.environ[name] = str(val)
            except Exception:
                pass
    return all(os.getenv(n) for n in NAMES)

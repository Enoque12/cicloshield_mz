"""Reparacao de nomes com acentos estragados (mojibake), ex.: 'Zambï¿½zia' -> 'Zambézia'.

Causas tipicas: texto UTF-8 lido como cp1252/latin-1 (muito comum no Windows) ou caracteres
ja corrompidos na fonte (U+FFFD). Nomes que nao se conseguem recuperar sozinhos ficam com '?'
e podem ser corrigidos em data/name_fixes.json, ex.: {"Ch?kw?": "Chókwè"}.
"""
import json
import re
import unicodedata

from pathlib import Path

from .config import DATA

PROVINCIAS = ["Cabo Delgado", "Gaza", "Inhambane", "Manica", "Maputo", "Maputo Cidade",
              "Maputo (província)", "Nampula", "Niassa", "Sofala", "Tete", "Zambézia"]

_overrides = None


def read_text(path) -> str:
    """Le texto em UTF-8 (com ou sem BOM) e, se falhar, em cp1252 (ficheiros gravados no Windows)."""
    b = Path(path).read_bytes()
    try:
        return b.decode("utf-8-sig")
    except UnicodeDecodeError:
        return b.decode("cp1252", errors="replace")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def undo_mojibake(s: str) -> str:
    """UTF-8 lido como cp1252/latin-1 -> texto certo. Texto ja correto fica igual."""
    if all(ord(c) < 128 for c in s):
        return s
    for enc in ("cp1252", "latin-1"):
        try:
            return s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return s


def _load_overrides() -> dict:
    global _overrides
    if _overrides is None:
        p = DATA / "name_fixes.json"
        _overrides = json.loads(read_text(p)) if p.exists() else {}
    return _overrides


def fix_name(s):
    if not isinstance(s, str):
        return s
    s = undo_mojibake(s).replace("\ufffd", "?")
    ov = _load_overrides()
    if s in ov:
        return ov[s]
    if "?" in s:   # tenta completar com a lista de provincias (ex.: 'Zamb?zia')
        pat = re.compile("^" + re.escape(s).replace(r"\?", ".") + "$", re.IGNORECASE)
        hits = [p for p in PROVINCIAS if pat.match(p)]
        if len(hits) == 1:
            return hits[0]
    f = _fold(s)    # poe acento em provincias que vieram sem ele (ex.: Natural Earth)
    for p in PROVINCIAS:
        if _fold(p) == f:
            return p
    return s


def unresolved(names):
    return sorted({n for n in names if isinstance(n, str) and "?" in n})

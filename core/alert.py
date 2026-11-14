"""Gerador de alerta SMS/USSD para telemoveis basicos."""
import json
import math
import unicodedata
from .config import DATA

# Alfabeto basico GSM 03.38 e extensao (cada char da extensao conta 2)
_GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_GSM_EXT = set("^{}\\[~]|€")

# Portugues: texto base. Sena e Makhuwa: SEM traducao automatica -> validar com falante nativo.
TEMPLATES = {
    "pt": "ALERTA CICLONE {nome}: chega a {distrito} em cerca de {horas}h. "
          "Va ao abrigo: {abrigo}. Leve documentos e agua. Evite pontes e rios. {contacto}",
    "sena": "[TRADUCAO SENA POR VALIDAR] {nome} {distrito} {horas}h {abrigo}",
    "makhuwa": "[TRADUCAO MAKHUWA POR VALIDAR] {nome} {distrito} {horas}h {abrigo}",
}
LANG_LABEL = {"pt": "Português", "sena": "Sena", "makhuwa": "Makhuwa"}


def load_templates() -> dict:
    """Se existir data/translations.json (preenchido por falante nativo), substitui os modelos."""
    t = dict(TEMPLATES)
    p = DATA / "translations.json"
    if p.exists():
        try:
            t.update({k: v for k, v in json.loads(p.read_text()).items() if v})
        except Exception:
            pass
    return t


def strip_accents(text: str) -> str:
    n = unicodedata.normalize("NFKD", text)
    return "".join(c for c in n if not unicodedata.combining(c))


def sms_stats(text: str) -> dict:
    if all(c in _GSM_BASIC or c in _GSM_EXT for c in text):
        units = sum(2 if c in _GSM_EXT else 1 for c in text)
        enc, single, multi = "GSM-7", 160, 153
    else:
        units, enc, single, multi = len(text), "UCS-2 (acentos!)", 70, 67
    segs = 1 if units <= single else math.ceil(units / multi)
    return {"encoding": enc, "chars": units, "segments": segs, "limit": single}


def build_message(template: str, nome: str, distrito: str, horas: int,
                  abrigo: str, contacto: str, sem_acentos: bool) -> str:
    msg = template.format(nome=nome, distrito=distrito, horas=horas,
                          abrigo=abrigo, contacto=contacto).strip()
    return strip_accents(msg) if sem_acentos else msg


def ussd_menu(nome: str, horas: int) -> str:
    return (f"CICLONE {nome}\n1. Meu distrito: risco\n2. Abrigo mais proximo\n"
            f"3. Rota segura\n4. Aviso em {horas}h\n0. Sair")

"""Lista os nomes de regioes ainda com caracteres por recuperar.  python scripts/check_names.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import data as dt
from core.textfix import unresolved

D = dt.load_districts()
if D is None:
    sys.exit("Sem data/districts.json")
names = [u["name"] for u in D["units"]] + [u["province"] for u in D["units"]]
bad = unresolved(names)
print(f"{len(D['units'])} regioes; {len(bad)} nomes por recuperar")
for n in bad:
    print("  ", n)
if bad:
    print('Cria data/name_fixes.json, ex.: {"Ch?kw?": "Chókwè"}')

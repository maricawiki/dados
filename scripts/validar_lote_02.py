#!/usr/bin/env python3
"""Verificação offline das cópias fiscais e previdenciárias do lote 02."""
import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
files=json.loads((ROOT/"lote-02.manifest.json").read_text(encoding="utf-8"))["files"]
assert len(files)==45
def load(n):
    return json.loads((ROOT/n).read_text(encoding="utf-8"))
for name, expected in files.items():
    assert Path(name).name==name and name.endswith((".csv",".json"))
    raw=(ROOT/name).read_bytes()
    assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==expected,name
    if name.endswith(".json"):
        load(name)
    else:
        s=raw.decode("utf-8")
        sep=";" if ";" in s.splitlines()[0] else ","
        rows=list(csv.reader(io.StringIO(s),delimiter=sep))
        assert len(rows)>1 and all(len(r)==len(rows[0]) for r in rows),name
for code in range(1,18):
    data=load(f"FIN-{code:03}.json")
    assert [r["ano"] for r in data["serie"]]==list(range(2019,2026))
for code in (15,16,17):
    for row in load(f"FIN-{code:03}.json")["serie"]:
        if row["ano"]==2023:
            assert row["valor"] is None and row["populacao_habitantes"] is None
        else:
            assert abs(Decimal(row["numerador_reais"])/Decimal(row["populacao_habitantes"])-Decimal(row["valor"]))<=Decimal("0.005")
for row in load("PREV-005.json")["serie"]:
    assert row["total_centavos"]==row["investimentos_centavos"]+row["disponibilidades_centavos"]
print("Lote 02: 45 hashes, formatos e conciliações básicas conferidos")

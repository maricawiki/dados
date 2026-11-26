#!/usr/bin/env python3
"""Verificação offline de Economia e Trabalho."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
files=json.loads((ROOT/"lote-03.manifest.json").read_text(encoding="utf-8"))["files"]
assert len(files)==92
assert sum(n.startswith("ECO-") for n in files)==20
assert sum(n.startswith("TRB-") for n in files)==72
for name, expected in files.items():
    assert Path(name).name==name and name.endswith((".csv",".json"))
    assert name.startswith(("ECO-","TRB-"))
    raw=(ROOT/name).read_bytes()
    assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==expected,name
    text=raw.decode("utf-8")
    if name.endswith(".json"):
        data=json.loads(text)
        assert isinstance(data,dict) and data.get("titulo"), name
    else:
        sep=";" if ";" in text.splitlines()[0] else ","
        rows=list(csv.reader(io.StringIO(text),delimiter=sep))
        assert len(rows)>1 and all(len(r)==len(rows[0]) for r in rows),name
for name in ("TRB-001.csv","TRB-002.csv","TRB-001-painel-onmt.csv","TRB-002-painel-onmt.csv"):
    with (ROOT/name).open(encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            assert int(row["admissoes"])-int(row["desligamentos"])==int(row["saldo"]),name
print("Lote 03: 92 hashes, formatos e saldos Caged conferidos")

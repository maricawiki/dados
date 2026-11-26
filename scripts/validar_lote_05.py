#!/usr/bin/env python3
"""Valida lote 05 offline."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
files=json.loads((ROOT/"lote-05.manifest.json").read_text(encoding="utf-8"))["files"]
assert len(files)==59
for prefix,count in {"SAN-":33,"MOB-":20,"TEL-":4,"TER-":2}.items():
    assert sum(n.startswith(prefix) for n in files)==count,prefix
for name, expected in files.items():
    assert Path(name).name==name and name.endswith((".csv",".json"))
    raw=(ROOT/name).read_bytes()
    assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==expected,name
    text=raw.decode("utf-8")
    if name.endswith(".json"):
        data=json.loads(text)
        assert isinstance(data,dict) and data.get("titulo"),name
    else:
        sep=";" if ";" in text.splitlines()[0] else ","
        rows=list(csv.reader(io.StringIO(text),delimiter=sep))
        assert len(rows)>1 and all(len(row)==len(rows[0]) for row in rows),name
for i in range(4,16):
    name=f"SAN-{i:03}.json"
    obj=json.loads((ROOT/name).read_text(encoding="utf-8"))
    assert str(obj["ano_referencia"])=="2023" and str(obj["edicao_sinisa"])=="2024",name
print("Lote 05: 59 hashes, formatos e referências SINISA conferidos")

#!/usr/bin/env python3
"""Valida Educação e Saúde sem consultas externas."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
files=json.loads((ROOT/"lote-04.manifest.json").read_text(encoding="utf-8"))["files"]
assert len(files)==43
assert sum(n.startswith("EDU-") for n in files)==32
assert sum(n.startswith("SAU-") for n in files)==11
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
for i in range(6,18):
    with (ROOT/f"EDU-{i:03}.csv").open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    assert len({r["ano"] for r in rows})==len(rows)
    for row in rows:
        for key,value in row.items():
            if key.endswith("_percentual") and value.strip() not in ("","-","--","—","NA","N/A"):
                assert 0<=float(value.replace(",","."))<=100,(i,key,value)
print("Lote 04: 43 hashes, formatos e limites das taxas de distorção conferidos")

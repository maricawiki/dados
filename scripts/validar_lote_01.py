#!/usr/bin/env python3
"""Valida o lote 01 sem rede."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "observatorio"
manifest = json.loads((ROOT / "lote-01.manifest.json").read_text(encoding="utf-8"))
files = manifest["files"]
assert len(files) == 21
def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))
def rows(name, delimiter=","):
    with (ROOT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))
for name, expected in files.items():
    assert Path(name).name == name and name.endswith((".json", ".csv"))
    data = (ROOT / name).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert actual == expected, name
    if name.endswith(".json"):
        load(name)
    else:
        assert rows(name, ";" if name.startswith("FROTA-") else ",")
for row in rows("DEM-002.csv"):
    p, q = int(row["populacao_inicial"]), int(row["populacao_final"])
    n = int(row["ano_final"]) - int(row["ano_inicial"])
    assert abs(100*(q/p-1)-float(row["variacao_total_percentual"])) < 0.000051
    assert abs(100*((q/p)**(1/n)-1)-float(row["taxa_media_anual_percentual"])) < 0.000051
for row in rows("DEM-006.csv"):
    assert abs(int(row["habitantes_nesses_domicilios"])/int(row["domicilios"])-float(row["media_moradores"])) < 0.00501
sex = rows("DEM-004-sexo-idade-2022.csv")
assert sum(int(r["populacao"]) for r in sex if r["sexo"]=="Homens") == 94835
assert sum(int(r["populacao"]) for r in sex if r["sexo"]=="Mulheres") == 102442
pop = {r["ano"]:r for r in load("POP-IBGE-MARICA-2014-2025.json")["serie"]}
fin = load("FIN-POP-IBGE-2019-2025.json")["serie"]
assert pop[2023]["populacao_habitantes"] is None
for r in fin:
    assert all(r[k]==pop[r["ano"]][k] for k in ("populacao_habitantes","tipo"))
assert [(int(r["ano"]),int(r["veiculos_registrados"])) for r in rows("FROTA-MARICA-ANUAL.csv",";")] == [(int(r["ano"]),r["frota"]) for r in load("FROTA-MARICA-ANUAL.json")["serie"]]
print("Lote 01: 21 hashes e consistência de séries conferidos")

#!/usr/bin/env python3
"""Valida Segurança Pública e a dependência SENATRAN offline."""
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
manifest=json.loads((ROOT/"lote-06.manifest.json").read_text(encoding="utf-8"))
files=manifest["files"]
deps=manifest["dependencias"]
assert len(files)==246
assert set(deps)=={"FROTA-MARICA-ANUAL.csv","FROTA-MARICA-ANUAL.json"}
def load(n):
    return json.loads((ROOT/n).read_text(encoding="utf-8"))
def rows(n):
    text=(ROOT/n).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text),delimiter=";" if ";" in text.splitlines()[0] else ","))
for name, expected in {**files,**deps}.items():
    assert Path(name).name==name and re.fullmatch(r"[0-9a-f]{40}",expected)
    raw=(ROOT/name).read_bytes()
    assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==expected,name
    if name.endswith(".json"):
        assert load(name).get("titulo"),name
    else:
        assert rows(name),name
special={2,14,23,32,33}
for i in range(1,52):
    code=f"SEG-{i:03}"
    a=load(code+".json")
    assert a["id"]==code and a["codigo_ibge"]=="3302700"
    observed=[(x["competencia"],x["registros"]) for x in a["serie"]]
    assert len(observed)>=120 and [k for k,v in observed]==sorted(set(k for k,v in observed))
    assert all(isinstance(v,int) and v>=0 for k,v in observed)
    assert observed==[(x["competencia"],int(x["registros"])) for x in rows(code+".csv")]
    if i in special:
        assert all(code+suffix not in files for suffix in ("-taxas.json","-taxa-mensal.csv","-taxa-anual.csv"))
        continue
    t=load(code+"-taxas.json")
    assert t["id"]==code and t["variavel_isp"]==a["variavel_isp"]
    assert t["unidade"]=="taxa por 100 mil habitantes"
    for period,suffix,key in (("mensal","-taxa-mensal.csv","competencia"),("anual","-taxa-anual.csv","ano")):
        series=t[period]
        assert series
        assert [(x["competencia"],Decimal(x["taxa"])) for x in series]==[(x[key],Decimal(x["taxa_por_100_mil_habitantes"].replace(",","."))) for x in rows(code+suffix)],code
        assert all(Decimal(x["taxa"])>=0 for x in series)
fleet={x["ano"]:x["frota"] for x in load("FROTA-MARICA-ANUAL.json")["serie"]}
assert fleet=={x["ano"]:int(x["veiculos_registrados"]) for x in rows("FROTA-MARICA-ANUAL.csv")}
for code in ("SEG-002","SEG-014","SEG-023"):
    v=load(code+"-taxa-frota.json")
    assert v["status"]=="taxa_derivada_nao_certificada_equivalente"
    assert len(v["serie"])==len(fleet)
    absolute=load(code+".json")["serie"]
    csvrows=rows(code+"-taxa-frota.csv")
    for x,y in zip(v["serie"],csvrows):
        year=x["ano"]
        counts=[z["registros"] for z in absolute if z["competencia"][:4]==year]
        assert len(counts)==12 and x["casos"]==sum(counts)==int(y["casos_isp"])
        assert year==y["ano"] and x["frota"]==fleet[year]==int(y["frota_renavam"])
        expected=(Decimal(x["casos"])*100000/Decimal(x["frota"])).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        assert Decimal(x["taxa_por_100_mil_veiculos"])==expected==Decimal(y["taxa_por_100_mil_veiculos"].replace(",","."))
print("Lote 06: 246 arquivos, 2 dependências, pares CSV/JSON e taxas por frota conferidos")

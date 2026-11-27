#!/usr/bin/env python3
"""ECO-001: propostas do PIB municipal oficial SIDRA 5938/v37.

Preserva a unidade mil reais, a referência 2010 e a série nominal.
Não calcula PIB per capita; alterações de 2022/2023 exigem revisão coordenada.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
URL="https://apisidra.ibge.gov.br/values/t/5938/n6/3302700/v/37/p/all"

def load(name):return json.loads((DATA/name).read_text(encoding="utf-8"))
def encode(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def fetch():
    with urlopen(Request(URL,headers={"Accept":"application/json","User-Agent":"MaricaWiki/1.0"}),timeout=55) as resp:
        loc=urlsplit(resp.geturl())
        if loc.scheme!="https" or loc.hostname!="apisidra.ibge.gov.br":raise ValueError("Redirecionamento fora da fonte")
        raw=resp.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError("Resposta SIDRA acima do limite")
        return json.loads(raw)

def parse(payload):
    if not isinstance(payload,list) or len(payload)<2:raise ValueError("Resposta SIDRA inválida")
    header=payload[0]
    # Ordem de dimensões pode mudar: identificar pelo rótulo oficial do cabeçalho.
    def field(label):
        hits=[k for k,v in header.items() if re.fullmatch(r"D\d+C",k) and isinstance(v,str) and label in v.casefold()]
        if len(hits)!=1:raise ValueError("Dimensão SIDRA não reconhecida: "+label)
        return hits[0]
    municipality=field("município")
    year=field("ano")
    variable=field("variável")
    result={}
    for row in payload[1:]:
        if row[municipality]!="3302700" or row[variable]!="37" or row.get("NC")!="6" or row.get("MN","").casefold()!="mil reais":
            raise ValueError("Município, variável ou unidade divergente")
        if not re.fullmatch(r"20\d{2}",row[year]):raise ValueError("Ano inválido")
        y=int(row[year])
        raw=row.get("V","")
        if not isinstance(raw,str) or not raw.isdigit() or int(raw)<=0 or y in result:
            raise ValueError("Valor ausente, inválido ou duplicado: "+str(y))
        result[y]=int(raw)
    years=sorted(result)
    if years!=list(range(2002,years[-1]+1)) or years[-1]>=date.today().year:
        raise ValueError("Série descontínua ou futuro")
    return {y:result[y] for y in years}

def serialize(values):
    output=io.StringIO(newline="")
    w=csv.writer(output,lineterminator="\n")
    w.writerow(["ano","pib_mil_reais","pib_reais","pib_bilhoes_reais","codigo_municipio","fonte"])
    for y,v in values.items():w.writerow([y,v,v*1000,f"{Decimal(v)/1000000:.6f}","3302700","IBGE_SIDRA_5938_v37"])
    return output.getvalue().encode("utf-8")

def propose(values):
    old=load("ECO-001.json")
    if old["id"]!="ECO-001" or old["codigo_ibge"]!="3302700" or old["fonte"]["api"]!=URL:
        raise ValueError("Identidade local divergente")
    with (DATA/"ECO-001.csv").open(encoding="utf-8",newline="") as fh:
        reference={int(x["ano"]):int(x["pib_mil_reais"]) for x in csv.DictReader(fh)}
    if not reference.keys()<=values.keys():raise ValueError("Série oficial perdeu cobertura")
    # ECO-002 continua oficial e pontual; não recalcular nem atualizar silenciosamente.
    if any(values[y]!=reference[y] for y in (2022,2023)):
        raise ValueError("Revisão PIB 2022/2023: conciliar ECO-002 antes de gerar proposta")
    raw=serialize(values)
    if raw==(DATA/"ECO-001.csv").read_bytes():return {}
    old["serie"].update(inicio=min(values),fim=max(values),observacoes=len(values))
    old["checagem"]=date.today().isoformat()
    files={"ECO-001.csv":raw,"ECO-001.json":encode(old)}
    manifest=load("lote-03.manifest.json")
    for name,data in files.items():
        if name not in manifest["files"]:raise ValueError("Fora do lote")
        manifest["files"][name]=blob(data)
    files["lote-03.manifest.json"]=encode(manifest)
    return files

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    values=parse(fetch())
    changes=propose(values)
    if changes:
        with tempfile.TemporaryDirectory(prefix="pib_proposta_") as tmp:
            root=Path(tmp)
            shutil.copytree(DATA,root/"observatorio")
            (root/"scripts").mkdir()
            for name,raw in changes.items():(root/"observatorio"/name).write_bytes(raw)
            test=root/"scripts/validar_lote_03.py"
            shutil.copy2(ROOT/"scripts"/test.name,test)
            subprocess.run([sys.executable,str(test)],check=True)
        if args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora da árvore")
            out.mkdir(parents=True,exist_ok=False)
            for name,raw in changes.items():(out/name).write_bytes(raw)
    print("PIB_PROPOSTA",len(values),"anos",min(values),max(values),len(changes),"arquivos; sem publicar",flush=True)

if __name__=="__main__":main()

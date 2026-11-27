#!/usr/bin/env python3
"""Propostas de ECO-005 (IBGE) e SAU-002 (CNES); nunca altera a base publicada."""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from produzir_cempre_cnae_fonte import parse,csvdata,get,PERIODS
from observatorio_saude_leitos_extrair import extract

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
DATE=datetime.now(timezone.utc).date().isoformat()
RUN=os.environ.get("GITHUB_RUN_ID")
FIELDS={
    "hospitais_com_leitos":"estabelecimentos_hospitalares_com_leitos",
    "leitos_existentes":"leitos_internacao_existentes",
    "leitos_sus":"leitos_internacao_sus",
    "uti_existentes":"leitos_uti_existentes",
    "uti_sus":"leitos_uti_sus",
}

def encode(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def load(name):return json.loads((DATA/name).read_text(encoding="utf-8"))
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def cnae():
    series,labels=parse()
    old=load("ECO-005.json")
    if old["id"]!="ECO-005" or old["codigo_ibge"]!="3302700":raise ValueError("Identidade")
    definitions=[{"secao":k,"codigo_categoria":x["codigo_categoria"],"nome":labels[k]} for k,x in ((v["secao"],v) for v in old["secoes"])]
    if definitions!=old["secoes"]:raise ValueError("Classificação CNAE divergente")
    # Detectar edição nova sem reinterpretar os anos de referência.
    latest=get(PERIODS["nova_2022_2024"]["url"].replace("p/2022-2024","p/all"))
    if not all(x.get("D1C")=="3302700" and x.get("D3C")=="2585" for x in latest):raise ValueError("Sondagem CNAE inválida")
    years=sorted({int(x["D2C"]) for x in latest})
    print("CNAE_NOVOS_ANOS",[y for y in years if y>2024],flush=True)
    raw=csvdata(series).encode("utf-8")
    if series==old["serie"] and raw==(DATA/"ECO-005.csv").read_bytes():return {}
    old["serie"]=series
    if RUN:old["fonte"]["consulta_execucao"]="https://github.com/maricawiki/dados/actions/runs/"+RUN
    return {"ECO-005.json":encode(old),"ECO-005.csv":raw}

def leitos(full=False):
    old=load("SAU-002.json")
    if old["id"]!="SAU-002" or old["codigo_municipio"]!="330270":raise ValueError("Identidade")
    with (DATA/"SAU-002.csv").open(encoding="utf-8",newline="") as fh:
        reader=csv.DictReader(fh)
        columns=reader.fieldnames
        rows=list(reader)
    years=[int(r["ano"]) for r in rows]
    if years!=list(range(2007,years[-1]+1)) or len(rows)!=old["serie"]["observacoes"]:raise ValueError("Cobertura local")
    # Revalidar os dois pontos oficiais do validador privado; auditoria total opcional.
    selected=years if full else sorted({2022,years[-1]})
    by_year={int(r["ano"]):r for r in rows}
    files={x["ano"]:x["url"] for x in old["fonte"]["arquivos"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(extract,selected))
    for x in results:
        y=x["ano"]
        if x["competencia"]!=y*100+12 or x["fonte"]!=files[y]:raise ValueError("Competência/fonte divergente")
        if x["hospitais_com_leitos"]<=0 or not all(type(x[k]) is int and x[k]>=0 for k in FIELDS):raise ValueError("Valor inválido")
        if x["leitos_sus"]>x["leitos_existentes"] or x["uti_sus"]>x["uti_existentes"]:raise ValueError("SUS maior que total")
        revised={field:str(x[k]) for k,field in FIELDS.items()}
        by_year[y].update(revised)
    buf=io.StringIO(newline="")
    writer=csv.DictWriter(buf,fieldnames=columns,lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw=buf.getvalue().encode("utf-8")
    if raw==(DATA/"SAU-002.csv").read_bytes():return {}
    old["verificado_em"]=DATE
    if RUN:old["fonte"]["consulta_execucao"]="https://github.com/maricawiki/dados/actions/runs/"+RUN
    return {"SAU-002.json":encode(old),"SAU-002.csv":raw}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("modo",choices=["cnae","leitos"])
    p.add_argument("--auditoria-completa",action="store_true")
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    lot="03" if args.modo=="cnae" else "04"
    changes=cnae() if lot=="03" else leitos(args.auditoria_completa)
    if changes:
        name=f"lote-{lot}.manifest.json"
        manifest=load(name)
        for filename,body in changes.items():
            if filename not in manifest["files"]:raise ValueError("Arquivo não autorizado")
            manifest["files"][filename]=blob(body)
        changes[name]=encode(manifest)
        with tempfile.TemporaryDirectory(prefix="proposta_agregados_") as temp:
            root=Path(temp)
            shutil.copytree(DATA,root/"observatorio")
            (root/"scripts").mkdir()
            for filename,body in changes.items():(root/"observatorio"/filename).write_bytes(body)
            target=root/"scripts"/f"validar_lote_{lot}.py"
            shutil.copy2(ROOT/"scripts"/target.name,target)
            subprocess.run([sys.executable,str(target)],check=True)
        if args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora do repositório")
            out.mkdir(parents=True,exist_ok=False)
            for filename,body in changes.items():(out/filename).write_bytes(body)
    print("AGREGADOS_PROPOSTA",args.modo,len(changes),"arquivos; sem publicar",flush=True)

if __name__=="__main__":main()

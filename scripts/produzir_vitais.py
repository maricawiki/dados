#!/usr/bin/env python3
"""SINASC/SIM: revisão coordenada dos indicadores SAU-004/005.

Revalida último ano consolidado da série atual (2010–2024).
Não incorpora 2025 ou 2026 sem comprovação de consolidação oficial.
Revisões de 2010/2022 exigem conciliação da natalidade censitária SAU-006.
"""
import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from estatisticas_vitais_fonte import read_and_count,file_url

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
YEARS=list(range(2010,2025))
PLAN={2014:1823,2021:2031,2022:2133,2023:2191,2024:2120}
def load(name):return json.loads((DATA/name).read_text(encoding="utf-8"))
def encode(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def reference():
    births=load("SAU-004.json")
    deaths=load("SAU-005.json")
    if any(x["codigo_ibge"]!="330270" or x["periodo"]!=[2010,2024] for x in (births,deaths)):
        raise ValueError("Cobertura ou município divergente")
    if any([r["ano"] for r in x["serie"]]!=YEARS for x in (births,deaths)):
        raise ValueError("Série incompleta")
    values={}
    for a,b in zip(births["serie"],deaths["serie"]):
        n=a["nascidos_vivos"];d=b["obitos_infantis"]
        if b["nascidos_vivos"]!=n or not 0<=d<=n or n<=0 or abs(b["taxa"]-1000*d/n)>1e-10:
            raise ValueError("Natalidade e mortalidade não conciliam")
        values[a["ano"]]=(n,d)
    return births,deaths,values

def get(year):
    a=read_and_count("SINASC",year)
    b=read_and_count("SIM",year)
    if a["url"]!=file_url("SINASC",year) or b["url"]!=file_url("SIM",year):
        raise ValueError("Fonte divergente")
    n=a["residentes_marica"];d=b["obito_infantil_categorias"].get("sim",0)
    if not 0<=d<=n or n<=0 or set(b["idade_anos_obitos_com_flag_infantil"])-{"000"}:
        raise ValueError("Contagens incompatíveis")
    # Preserva o controle histórico do validador editorial.
    if b["obito_fetal_categorias"].get("sim",0)!=0:
        raise ValueError("Mudança na composição dos registros SIM; revisar antes de propor")
    return year,(n,d)

def serialize(values):
    a=io.StringIO(newline="");b=io.StringIO(newline="")
    wa=csv.writer(a,lineterminator="\n");wb=csv.writer(b,lineterminator="\n")
    wa.writerow(["ano","nascidos_vivos","municipio_residencia","fonte_id"])
    wb.writerow(["ano","obitos_menores_1_ano","nascidos_vivos","taxa_por_mil","municipio_residencia","fonte_id"])
    for y,(n,d) in sorted(values.items()):
        wa.writerow([y,n,"330270",f"SINASC_SESRJ_DNRJ_{y}"])
        wb.writerow([y,d,n,f"{1000*d/n:.4f}","330270",f"SIM_SINASC_SESRJ_{y}"])
    return a.getvalue().encode(),b.getvalue().encode()

def propose(revised):
    births,deaths,old=reference()
    values=dict(old)
    for year,(n,d) in revised.items():
        if year not in old or not 0<=d<=n or n<=0:raise ValueError("Exercício não consolidado ou inválido")
        if year in (2010,2022) and n!=old[year][0]:
            raise ValueError("Denominador censitário SAU-006 requer revisão coordenada")
        values[year]=(n,d)
    a,b=serialize(values)
    if values==old:
        if a!=(DATA/"SAU-004.csv").read_bytes() or b!=(DATA/"SAU-005.csv").read_bytes():
            raise ValueError("CSV histórico diverge do JSON")
        return {}
    for meta in (births,deaths):
        meta["conferencia"]=date.today().isoformat()
        meta["revisoes_divergentes_entre_fontes"]=[{"ano":y,"arquivo_estadual_atual":values[y][0],"plano_municipal":v,"diferenca":values[y][0]-v} for y,v in PLAN.items()]
    births["serie"]=[{"ano":y,"nascidos_vivos":n} for y,(n,d) in sorted(values.items())]
    deaths["serie"]=[{"ano":y,"obitos_infantis":d,"nascidos_vivos":n,"taxa":1000*d/n} for y,(n,d) in sorted(values.items())]
    changes={"SAU-004.csv":a,"SAU-005.csv":b,"SAU-004.json":encode(births),"SAU-005.json":encode(deaths)}
    manifest=load("lote-04.manifest.json")
    for name,raw in changes.items():manifest["files"][name]=blob(raw)
    changes["lote-04.manifest.json"]=encode(manifest)
    return changes

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--auditoria-completa",action="store_true")
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    selected=YEARS if args.auditoria_completa else [YEARS[-1]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        revised=dict(pool.map(get,selected))
    changes=propose(revised)
    if changes:
        with tempfile.TemporaryDirectory(prefix="vitais_proposta_") as tmp:
            root=Path(tmp)
            shutil.copytree(DATA,root/"observatorio")
            (root/"scripts").mkdir()
            for name,raw in changes.items():(root/"observatorio"/name).write_bytes(raw)
            test=root/"scripts/validar_lote_04.py"
            shutil.copy2(ROOT/"scripts"/test.name,test)
            subprocess.run([sys.executable,str(test)],check=True)
        if args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora da árvore")
            out.mkdir(parents=True,exist_ok=False)
            for name,raw in changes.items():(out/name).write_bytes(raw)
    print("VITAIS_PROPOSTA",selected,len(changes),"arquivos; sem publicar; somente anos consolidados atuais",flush=True)
if __name__=="__main__":main()

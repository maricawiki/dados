#!/usr/bin/env python3
"""Produzir propostas ISP-RJ, sem alterar arquivos publicados ou fichas."""
import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from isp_registros_fonte import SPEC, SERIES_START, read_official
from isp_taxas_fonte import _read

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
DATE=datetime.now(timezone.utc).date().isoformat()
MANIFEST="lote-06.manifest.json"

def load(name):
    return json.loads((DATA/name).read_text(encoding="utf-8"))

def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")

def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def compare(old,new,key,tag):
    a={x["competencia"]:x[key] for x in old}
    b={x["competencia"]:x[key] for x in new}
    if len(a)!=len(old) or len(b)!=len(new) or not a.keys()<=b.keys():
        raise ValueError("Cobertura ou duplicidade: "+tag)
    return a!=b

def propose_counts():
    rows,sha,charset=read_official()
    changed={}
    for code,_,_,field in SPEC:
        name=code+".json"
        old=load(name)
        if old["id"]!=code or old["variavel_isp"]!=field or old["codigo_ibge"]!="3302700":
            raise ValueError("Identidade incorreta "+code)
        series=[{"competencia":r["competencia"],"registros":r[field]} for r in rows
                if r[field] is not None and r["competencia"]>=SERIES_START.get(field,"2014-01")]
        if not compare(old["serie"],series,"registros",code):continue
        old["serie"]=series
        old["periodo_disponivel"]=f'{series[0]["competencia"]}–{series[-1]["competencia"]}'
        old["fonte"].update(sha256=sha,encoding=charset,extracao_utc=DATE)
        changed[name]=encode(old)
        out=io.StringIO(newline="")
        writer=csv.writer(out,lineterminator="\n")
        writer.writerow(["competencia","registros"])
        writer.writerows((x["competencia"],x["registros"]) for x in series)
        changed[code+".csv"]=out.getvalue().encode("utf-8")
    # Atualizar também as três taxas por frota se os numeradores históricos mudarem.
    fleet=load("FROTA-MARICA-ANUAL.json")["serie"]
    for code in ("SEG-002","SEG-014","SEG-023"):
        if code+".json" not in changed:continue
        counts=json.loads(changed[code+".json"])
        name=code+"-taxa-frota.json"
        old=load(name)
        series=[]
        for f in fleet:
            year=f["ano"]
            values=[x for x in counts["serie"] if x["competencia"][:4]==year]
            if [x["competencia"] for x in values]!=[f"{year}-{i:02d}" for i in range(1,13)]:
                raise ValueError("Frota sem 12 meses ISP: "+code+"/"+year)
            n=sum(x["registros"] for x in values)
            rate=(Decimal(n)*100000/Decimal(f["frota"])).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
            series.append({"ano":year,"casos":n,"frota":f["frota"],"taxa_por_100_mil_veiculos":str(rate)})
        old.update(serie=series,fonte_registros_isp=counts["fonte"])
        changed[name]=encode(old)
        changed[code+"-taxa-frota.csv"]=("ano;casos_isp;frota_renavam;taxa_por_100_mil_veiculos\n"+"".join(
            f'{x["ano"]};{x["casos"]};{x["frota"]};{x["taxa_por_100_mil_veiculos"].replace(".",",")}\n' for x in series)).encode("utf-8")
    return changed

def propose_rates():
    m,mm=_read("mensal")
    a,am=_read("anual")
    changed={}
    for code,_,_,field in SPEC:
        name=code+"-taxas.json"
        if not (DATA/name).exists():continue
        old=load(name)
        if old["id"]!=code or old["variavel_isp"]!=field or old["unidade"]!="taxa por 100 mil habitantes":
            raise ValueError("Identidade de taxa incorreta: "+code)
        if field=="registro_ocorrencias" and (not any(field in x for x in m.values()) or not any(field in x for x in a.values())):
            print("SEG-024 preservado: variável ausente na fonte; não imputar",flush=True)
            continue
        cutoff=SERIES_START.get(field,"2014-01")
        monthly=[{"competencia":k,"taxa":v[field]} for k,v in sorted(m.items()) if k>=cutoff and v.get(field) is not None]
        annual=[{"competencia":k,"taxa":v[field]} for k,v in sorted(a.items()) if k>=cutoff[:4] and v.get(field) is not None and not(field in ("roubo_bicicleta","furto_bicicleta") and k=="2015")]
        cm=compare(old["mensal"],monthly,"taxa",code+"/mensal")
        ca=compare(old["anual"],annual,"taxa",code+"/anual")
        if not (cm or ca):continue
        old.update(mensal=monthly,anual=annual)
        old["fonte"].update(taxas_mensais=mm,taxas_anuais=am,extracao_utc=DATE)
        changed[name]=encode(old)
        changed[code+"-taxa-mensal.csv"]=("competencia;taxa_por_100_mil_habitantes\n"+"".join(
            f'{x["competencia"]};{x["taxa"].replace(".",",")}\n' for x in monthly)).encode("utf-8")
        changed[code+"-taxa-anual.csv"]=("ano;taxa_por_100_mil_habitantes\n"+"".join(
            f'{x["competencia"]};{x["taxa"].replace(".",",")}\n' for x in annual)).encode("utf-8")
    return changed

def validate_candidate(changed):
    manifest=load(MANIFEST)
    for name,raw in changed.items():
        if name not in manifest["files"] or Path(name).name!=name:
            raise ValueError("Arquivo não autorizado "+name)
        manifest["files"][name]=blob(raw)
    if not changed:return {}
    result={**changed,MANIFEST:encode(manifest)}
    with tempfile.TemporaryDirectory(prefix="isp_proposta_") as tmp:
        root=Path(tmp)
        shutil.copytree(DATA,root/"observatorio")
        (root/"scripts").mkdir()
        shutil.copy2(ROOT/"scripts/validar_lote_06.py",root/"scripts/validar_lote_06.py")
        for name,raw in result.items():(root/"observatorio"/name).write_bytes(raw)
        subprocess.run([sys.executable,str(root/"scripts/validar_lote_06.py")],check=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("modo",choices=["registros","taxas"])
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    result=validate_candidate(propose_counts() if args.modo=="registros" else propose_rates())
    if result and args.propor:
        out=args.propor.resolve()
        if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora do repositório")
        out.mkdir(parents=True,exist_ok=False)
        for name,data in result.items():(out/name).write_bytes(data)
    print("ISP_PROPOSTA",args.modo,"arquivos",len(result),"; revisão antes de publicar",flush=True)

if __name__=="__main__":
    main()

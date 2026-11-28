#!/usr/bin/env python3
"""Revalida os 12 indicadores oficiais de distorção idade-série (EDU-006–017).
Sem microdados, sem atualização silenciosa, sem interpolação de lacunas.
Novos anos são detectados no catálogo oficial e exigem revisão das 12 fichas.
"""
import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from inep_distorcao_fonte import year_data,KEYS,NETWORKS,BASE

DATA=Path(__file__).resolve().parents[1]/"observatorio"
PAGE="https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-distorcao-idade-serie"
NAMES=dict(zip(NETWORKS,("total","municipal","estadual","federal","privada")))

def baseline():
    expected={}
    for i,key in enumerate(KEYS,start=6):
        code=f"EDU-{i:03d}"
        meta=json.loads((DATA/(code+".json")).read_text(encoding="utf-8"))
        if meta["codigo_ibge"]!="3302700" or meta["variavel_inep"]!=key:raise ValueError(code)
        with (DATA/(code+".csv")).open(encoding="utf-8",newline="") as f:csvrows=list(csv.DictReader(f))
        if len(csvrows)!=len(meta["serie"]) or [x["ano"] for x in meta["serie"]]!=list(range(2016,2026)):raise ValueError("Cobertura divergente")
        for c,j in zip(csvrows,meta["serie"]):
            y=j["ano"]
            sha=j["sha256_zip"];url=j["fonte"]
            if not re.fullmatch(r"[0-9a-f]{64}",sha) or url!=BASE.format(y=y):raise ValueError("Proveniência inválida")
            if int(c["ano"])!=y or c["fonte_ano"]!=url:raise ValueError("CSV/JSON divergentes")
            entry=expected.setdefault(y,{"sha256_zip":sha,"fonte":url,"redes":{k:{} for k in NETWORKS}})
            if entry["sha256_zip"]!=sha or entry["fonte"]!=url:raise ValueError("Hashes divergentes")
            for k,n in NAMES.items():
                val=j[n];raw=c[n+"_percentual"]
                if (val is None and raw!="") or (val is not None and (not raw or float(raw)!=val or not 0<=val<=100)):raise ValueError("Taxa inválida")
                entry["redes"][k][key]=val
    return expected

def compare(actual,expected):
    if any(actual[k]!=expected[k] for k in ("fonte","sha256_zip","redes")):raise ValueError("Taxas ou origem divergentes: revisão editorial necessária")
def discover_once():
    with urlopen(Request(PAGE,headers={"User-Agent":"MaricaWiki/1.0"}),timeout=45) as r:
        loc=urlsplit(r.geturl())
        if loc.scheme!="https" or loc.hostname!="www.gov.br":raise ValueError("Catálogo INEP divergente")
        raw=r.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError("Catálogo acima do limite")
    html=raw.decode("utf-8")
    # Só URLs do padrão oficial municipal, não qualquer número no HTML.
    return sorted(set(int(y) for y in re.findall(r"TDI_(20\d{2})_MUNICIPIOS\.zip",html,re.I)))
def discover():
    for attempt in range(3):
        try:return discover_once()
        except OSError:
            if attempt==2:raise
            time.sleep(2*(attempt+1))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--auditoria-completa",action="store_true")
    p.add_argument("--somente-catalogo",action="store_true")
    a=p.parse_args()
    values=baseline()
    selected=[] if a.somente_catalogo else sorted(values) if a.auditoria_completa else [max(values)]
    for y in selected:
        compare(year_data(y,values[y]["sha256_zip"]),values[y])
        print("INEP_TDI_OK",y,"12 indicadores; 5 redes; hash confirmado",flush=True)
    if not a.somente_catalogo:
        print("INEP_TDI_REVALIDACAO",selected,"sem alteração",flush=True)
        return
    catalog=discover()
    if not catalog:raise ValueError("Catálogo sem links municipais reconhecíveis; revisar fonte")
    new=[y for y in catalog if y>max(values)]
    if new:print("::warning::Novos exercícios INEP para revisão editorial: "+str(new))
    print("INEP_TDI_MONITOR",json.dumps({"revalidados":selected,"anos_catalogo":catalog,"novos":new}),flush=True)
if __name__=="__main__":main()

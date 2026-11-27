#!/usr/bin/env python3
"""Sondagem independente dos registros e taxas ISP-RJ; nenhuma gravação."""
import argparse
import json
from pathlib import Path
from isp_registros_fonte import SPEC, SERIES_START, read_official
from isp_taxas_fonte import _read

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
def load(n):
    return json.loads((ROOT/n).read_text(encoding="utf-8"))
def compare(previous, current, code, kind):
    old={x["competencia"]:x["taxa" if kind!="registros" else "registros"] for x in previous}
    new={x["competencia"]:x["taxa" if kind!="registros" else "registros"] for x in current}
    if not old.keys() <= new.keys():
        raise ValueError(f"{code}/{kind}: perda de cobertura, revisão necessária")
    changed=sum(new[k]!=v for k,v in old.items())
    print(f"{code}/{kind}: {min(new)}–{max(new)}; novas competências={len(new.keys()-old.keys())}; revisões={changed}")
def monitor_registros():
    rows,sha,codec=read_official()
    print(f"Fonte registros SHA256={sha}; {codec}; {rows[0]['competencia']}–{rows[-1]['competencia']}")
    for code,title,slug,field in SPEC:
        current=[{"competencia":x["competencia"],"registros":x[field]} for x in rows if x[field] is not None and x["competencia"]>=SERIES_START.get(field,"2014-01")]
        compare(load(code+".json")["serie"],current,code,"registros")
def monitor_taxas():
    monthly,mm=_read("mensal")
    annual,am=_read("anual")
    print(f"Fonte taxas mensal {mm['inicio']}–{mm['fim']}; SHA256={mm['sha256']}; anual {am['inicio']}–{am['fim']}; SHA256={am['sha256']}")
    for code,title,slug,field in SPEC:
        path=ROOT/(code+"-taxas.json")
        if not path.exists():
            continue
        old=load(path.name)
        if field=="registro_ocorrencias" and (not any(field in x for x in monthly.values()) or not any(field in x for x in annual.values())):
            print(f"::warning::{code}: fonte sem variável; manter as duas séries anteriores e sua proveniência")
            continue
        cutoff=SERIES_START.get(field,"2014-01")
        m=[{"competencia":k,"taxa":v[field]} for k,v in sorted(monthly.items()) if k>=cutoff and v.get(field) is not None]
        a=[{"competencia":k,"taxa":v[field]} for k,v in sorted(annual.items()) if k>=cutoff[:4] and v.get(field) is not None and not (field in ("roubo_bicicleta","furto_bicicleta") and k=="2015")]
        compare(old["mensal"],m,code,"mensal")
        compare(old["anual"],a,code,"anual")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("modo",choices=["registros","taxas"])
    args=parser.parse_args()
    {"registros":monitor_registros,"taxas":monitor_taxas}[args.modo]()

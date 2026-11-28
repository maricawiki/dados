#!/usr/bin/env python3
"""Regenera oito séries de vínculos e duas de estabelecimentos do espelho ONMT auditado; não publica."""
import argparse,json
from pathlib import Path
from rais_vinculos_base import ROOT,ASSETS,CATEGORIES,retrieve,extract,csv_string
from rais_vinculos_recortes import SPECS,collect
from rais_estabelecimentos import extract_estabelecimentos,csv_text,PORTES

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    source,temp=retrieve()
    try:
        data,_=extract(source)
        data.update(collect(source))
        data.update(extract_estabelecimentos(source))
    finally:
        if temp:
            source.unlink(missing_ok=True)
            source.parent.rmdir()
    changed=[]
    candidate={}
    for code,rows in data.items():
        kind=(CATEGORIES[code] if code in CATEGORIES else SPECS[code])[3] if code.startswith("TRB-") else ("total" if code=="ECO-006" else "variacao")
        old=json.loads((ASSETS/(code+".json")).read_text(encoding="utf-8"))
        if old["id"]!=code:
            raise ValueError("ID divergente")
        raw=csv_text(rows,kind) if code in ("ECO-006","ECO-007") else csv_string(rows,kind)
        if rows!=old["serie"] or raw!=(ASSETS/(code+".csv")).read_bytes().decode("utf-8"):
            changed.append(code)
            old["serie"]=rows
        candidate[code+".json"]=json.dumps(old,ensure_ascii=False,indent=2)+"\n"
        candidate[code+".csv"]=raw
    if args.propor:
        out=args.propor.resolve()
        if out==ROOT or ROOT in out.parents:
            raise ValueError("Proposta deve estar fora do repositório")
        out.mkdir(parents=True,exist_ok=False)
        for name,content in candidate.items():
            (out/name).write_text(content,encoding="utf-8")
    if changed:
        raise SystemExit("RAIS_REVISAR: "+", ".join(changed))
    print("RAIS_OK: oito séries de vínculos e duas de estabelecimentos, 2014–2025, espelho SHA fixo; somente vínculos conciliados ao MTE")

if __name__=="__main__":
    main()

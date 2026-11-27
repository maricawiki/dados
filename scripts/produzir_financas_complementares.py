#!/usr/bin/env python3
"""FIN-012 a FIN-017: propostas de royalties, dívida e valores per capita."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from produzir_dca import ROOT, ASSETS
import financas_royalties_divida as dca
import financas_percapita as pc

def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")

def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("modo",choices=["percapita","royalties-divida"])
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    data=pc.extract() if args.modo=="percapita" else dca.extract()
    changed={}
    for code,rows in data.items():
        name=code+".json"
        old=json.loads((ASSETS/name).read_text(encoding="utf-8"))
        if old["id"]!=code or old["codigo_ibge"]!="3302700":
            raise ValueError("Identidade divergente")
        raw=(pc.csv_file(rows) if args.modo=="percapita" else dca.csv_data(rows,dca.SPECS[code][3])).encode("utf-8")
        if rows==old["serie"] and raw==(ASSETS/(code+".csv")).read_bytes():continue
        old["serie"]=rows
        if os.environ.get("GITHUB_RUN_ID"):
            provenance="https://github.com/maricawiki/dados/actions/runs/"+os.environ["GITHUB_RUN_ID"]
            if args.modo=="percapita":old["fontes"]["execucao_integracao"]=provenance
            else:old["fonte"]["consulta_execucao"]=provenance
        changed[name]=encode(old)
        changed[code+".csv"]=raw
    if changed:
        manifest="lote-02.manifest.json"
        m=json.loads((ASSETS/manifest).read_text(encoding="utf-8"))
        for name,raw in changed.items():
            if name not in m["files"]:raise ValueError("Arquivo fora do lote")
            m["files"][name]=blob(raw)
        changed[manifest]=encode(m)
        with tempfile.TemporaryDirectory(prefix="financas_proposta_") as tmp:
            root=Path(tmp)
            shutil.copytree(ASSETS,root/"observatorio")
            (root/"scripts").mkdir()
            for name,raw in changed.items():(root/"observatorio"/name).write_bytes(raw)
            test=root/"scripts/validar_lote_02.py"
            shutil.copy2(ROOT/"scripts/validar_lote_02.py",test)
            subprocess.run([sys.executable,str(test)],check=True)
        if args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora da árvore")
            out.mkdir(parents=True,exist_ok=False)
            for name,raw in changed.items():(out/name).write_bytes(raw)
    print("FIN_PROPOSTA",args.modo,len(changed),"arquivos; revisão necessária se alterados")

if __name__=="__main__":
    main()

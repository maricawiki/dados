#!/usr/bin/env python3
"""Exclusividade da origem CADPREV para PREV-001 a PREV-005."""
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]/"observatorio"
def check_url(url):
    x=urlsplit(url)
    assert x.scheme=="https" and x.hostname=="apicadprev.trabalho.gov.br",url
def main():
    for i in range(1,5):
        code=f"PREV-{i:03}"
        meta=json.loads((ROOT/(code+".json")).read_text(encoding="utf-8"))
        assert meta["fonte"]=="Ministério da Previdência Social — API CADPREV/DRAA"
        assert len(meta["proveniencia"])==len(meta["serie"])==len(meta["proveniencia_api"])
        for row,prov,api in zip(meta["serie"],meta["proveniencia"],meta["proveniencia_api"]):
            assert row["draa"]==prov["referencia"]==api["referencia"]
            for record in (row,prov,api):check_url(record["url"])
            assert row["url"]==prov["url"]==api["url"]
            assert row["status"]==prov["status"]==api["status"]=="Documentos Digitalizados"
            assert row["dt_envio"]==prov["dt_envio"]==api["dt_envio"]
            for k in ("ativos","aposentados","pensionistas"):
                assert sum(p[k] for p in api["planos"].values())==row[k]
        with (ROOT/(code+".csv")).open(encoding="utf-8",newline="") as f:
            for row in csv.DictReader(f):check_url(row["url"])
    with (ROOT/"PREV-001-planos.csv").open(encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):check_url(row["fonte_mps_url"])
    portfolio=json.loads((ROOT/"PREV-005.json").read_text(encoding="utf-8"))
    assert portfolio["fonte"]=="Ministério da Previdência Social — API CADPREV"
    print("PREV: proveniência exclusiva CADPREV, totais e planos reconciliados")
if __name__=="__main__":main()

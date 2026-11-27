#!/usr/bin/env python3
"""Sondagem em modo somente leitura: IBGE/SIDRA, domicílios e saneamento de Maricá."""
from __future__ import annotations
import json
import urllib.request
import urllib.error
import time

# NÃO incorporar números antes de selecionar as categorias e validar o denominador.
# Censo 2022: tabelas de domicílios particulares permanentes ocupados.
# Censo 2000/2010: categorias e universos podem ter nomes diferentes.
TABELAS = {
    # Explicit categories; 2022 totals are 73.454, 2010 totals 42.810.
    "agua_2022": "https://apisidra.ibge.gov.br/values/t/6803/n6/3302700/v/381/p/2022/c1821/all",
    "esgoto_2022": "https://apisidra.ibge.gov.br/values/t/6805/n6/3302700/v/381/p/2022/c11558/all",
    "lixo_2022": "https://apisidra.ibge.gov.br/values/t/6892/n6/3302700/v/381/p/2022/c67/all",
    "agua_2010": "https://apisidra.ibge.gov.br/values/t/1398/n6/3302700/v/96/p/2010/c61/all",
    "esgoto_2010": "https://apisidra.ibge.gov.br/values/t/1394/n6/3302700/v/96/p/2010/c11558/all",
    "lixo_2010": "https://apisidra.ibge.gov.br/values/t/1395/n6/3302700/v/96/p/2010/c67/all",
    "lixo_2000": "https://apisidra.ibge.gov.br/values/t/1439/n6/3302700/v/96/p/2000/c67/all",
}
# Evitar endpoint p/2022/c/all não aceito para algumas tabelas;
# o fallback n6/.../v/381/p/2022 recupera classificações padrão.
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"MaricaWiki-Observatorio/1.0; pesquisa de fontes IBGE"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)

def main():
    results={}
    for key,url in TABELAS.items():
        print("SOURCE",key,url,flush=True)
        try:
            data=fetch(url)
        except (urllib.error.URLError,ValueError,TimeoutError) as exc:
            print("SOURCE_ERR",key,type(exc).__name__,str(exc)[:300],flush=True)
            if key.endswith("2022"):
                fallback=url.split("/c/")[0].split("/c11558/")[0]
                try:
                    print("FALLBACK",key,fallback,flush=True)
                    data=fetch(fallback)
                except Exception as e:
                    print("FALLBACK_ERR",key,str(e)[:200],flush=True)
                    continue
            else:continue
        if not isinstance(data,list) or not data:print("BAD_FORMAT",key,str(data)[:200],flush=True);continue
        print("HEADER",key,json.dumps(data[0],ensure_ascii=False),flush=True)
        print("COUNT",key,len(data)-1,flush=True)
        for row in data[1:120]:
            print("ROW",key,json.dumps(row,ensure_ascii=False),flush=True)
        results[key]=len(data)-1
        time.sleep(.25)
    print("FINISHED",json.dumps(results),flush=True)
    if len(results)<3:raise SystemExit("Insufficient official data")
if __name__=="__main__":main()

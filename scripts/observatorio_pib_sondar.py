#!/usr/bin/env python3
"""Obtém série do PIB municipal de Maricá do IBGE/SIDRA (somente leitura)."""
import json
import urllib.request

URL="https://apisidra.ibge.gov.br/values/t/5938/n6/3302700/v/37/p/all"
r=urllib.request.Request(URL,headers={"User-Agent":"MaricaWiki-Observatorio/1.0 (serie-historica; consulta publica)"})
with urllib.request.urlopen(r,timeout=55) as resp:
    data=json.load(resp)
assert isinstance(data,list) and len(data)>12,(type(data),len(data))
print("IBGE_PIB_HEADER",json.dumps(data[0],ensure_ascii=False),flush=True)
for row in data[1:]:
    print("IBGE_PIB_ROW",json.dumps(row,ensure_ascii=False),flush=True)
print("IBGE_PIB_TOTAL_ROWS",len(data)-1,flush=True)

#!/usr/bin/env python3
"""Compara cobertura da API CNES atual com API histórica e arquivo oficial.

Nenhum dado cadastral bruto é salvo ou mostrado: imprime só totais e esquema.
"""
from __future__ import annotations
import json, urllib.parse, urllib.request, urllib.error
CASES=[
("cnes_atual_6_ativo","/cnes/estabelecimentos",{"codigo_municipio":330270,"status":1,"limit":20,"offset":0}),
("cnes_atual_6_todos","/cnes/estabelecimentos",{"codigo_municipio":330270,"limit":20,"offset":0}),
("cnes_atual_7","/cnes/estabelecimentos",{"codigo_municipio":3302700,"limit":20,"offset":0}),
("assistencia_sem_comp","/assistencia-a-saude/cnes-estabelecimentos",{"co_ibge":330270,"limit":20,"offset":0}),
("assistencia_comp_page_0","/assistencia-a-saude/cnes-estabelecimentos",{"co_ibge":330270,"nu_comp":202512,"limit":20,"offset":0}),
("assistencia_comp_page_1","/assistencia-a-saude/cnes-estabelecimentos",{"co_ibge":330270,"nu_comp":202512,"limit":20,"offset":1}),
("assistencia_comp_7","/assistencia-a-saude/cnes-estabelecimentos",{"co_ibge":3302700,"nu_comp":202512,"limit":20,"offset":0}),
]
HEADERS={"User-Agent":"MaricaWiki-Observatorio/1.0 (auditoria-publica)"}
def fetch(name,route,params):
    url="https://apidadosabertos.saude.gov.br"+route+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=50) as resp:data=json.load(resp)
    if isinstance(data,dict):
        detail={}
        for k,v in data.items():
            if isinstance(v,list):
                fields=sorted(v[0]) if v and isinstance(v[0],dict) else []
                detail[k]={"linhas_pagina":len(v),"campos":fields[:40],
                           "codigos_municipais_distribuicao":list(sorted(set(str(x.get("codigo_municipio",x.get("co_ibge",""))) for x in v)))[:10]}
            elif isinstance(v,(str,int,float,bool)):
                detail[k]=v
            else:detail[k]=str(type(v))
        print("COBERTURA",name,json.dumps(detail,ensure_ascii=False),flush=True)
    else:
        print("COBERTURA",name,"type",type(data).__name__,"size",len(data) if isinstance(data,list) else "-",flush=True)
def head(url):
    req=urllib.request.Request(url,headers=HEADERS,method="HEAD")
    try:
        with urllib.request.urlopen(req,timeout=30) as res:
            print("ARQUIVO",res.status,"bytes",res.headers.get("Content-Length"),
                  "type",res.headers.get("Content-Type"),"url",url,flush=True)
    except Exception as exc:
        print("ARQUIVO_ERR",type(exc).__name__,str(exc)[:140],flush=True)
if __name__=="__main__":
    for name,route,params in CASES:
        try:fetch(name,route,params)
        except Exception as exc:print("COBERTURA_ERR",name,type(exc).__name__,str(exc)[:200],flush=True)
    for u in [
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2025.zip",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_2024.csv",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_json.zip",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_csv.zip",
    ]:head(u)

#!/usr/bin/env python3
"""Monitor de denominadores IBGE: não troca Censo por estimativa.

O lote 01 alimenta finanças per capita, segurança e indicadores censitários.
Revisões e anos novos exigem conciliação dos lotes dependentes. Não escreve dados.
"""
import argparse
import csv
import json
import re
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]/"observatorio"
EST="https://apisidra.ibge.gov.br/values/t/6579/n6/3302700/v/9324/p/all"
CENSO="https://apisidra.ibge.gov.br/values/t/4714/n6/3302700/v/93/p/2022"
def fetch(url):
    with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"MaricaWiki/1.0"}),timeout=55) as resp:
        dst=urlsplit(resp.geturl())
        if dst.scheme!="https" or dst.hostname!="apisidra.ibge.gov.br":raise ValueError("Fonte divergente")
        data=resp.read(500_001)
        if len(data)>500_000:raise ValueError("Resposta acima do limite")
        return json.loads(data)
def parse(payload,var):
    if not isinstance(payload,list) or len(payload)<2:raise ValueError("Resposta inválida")
    header=payload[0]
    def field(label):
        hits=[k for k,v in header.items() if re.fullmatch(r"D\d+C",k) and isinstance(v,str) and label in v.casefold()]
        if len(hits)!=1:raise ValueError("Dimensão desconhecida: "+label)
        return hits[0]
    city,variable,year=field("município"),field("variável"),field("ano")
    values={}
    for row in payload[1:]:
        if row.get("NC")!="6" or row[city]!="3302700" or row[variable]!=var or row.get("MN","").casefold() not in ("pessoas","habitantes"):
            raise ValueError("Município, variável ou unidade incorretos")
        if not re.fullmatch(r"[12]\d{3}",row[year]):raise ValueError("Ano inválido")
        y=int(row[year])
        raw=row.get("V","")
        if y in values:raise ValueError("Ano duplicado")
        if raw in ("...","-","X",".."):values[y]=None
        elif isinstance(raw,str) and raw.isdigit() and 0<int(raw)<10_000_000:values[y]=int(raw)
        else:raise ValueError("Valor desconhecido")
    return values

def refs():
    data=json.loads((ROOT/"POP-IBGE-MARICA-2014-2025.json").read_text())
    fiscal=json.loads((ROOT/"FIN-POP-IBGE-2019-2025.json").read_text())
    if data["codigo_ibge"]!="3302700" or fiscal["codigo_ibge"]!="3302700":raise ValueError("Município")
    rows={r["ano"]:r for r in data["serie"]}
    if len(rows)!=len(data["serie"]):raise ValueError("Anos duplicados")
    for r in fiscal["serie"]:
        if any(r[k]!=rows[r["ano"]][k] for k in ("tipo","populacao_habitantes")):raise ValueError("Denominadores divergentes")
    if rows[2023]["populacao_habitantes"] is not None or rows[2022]["tipo"]!="censo_demografico_2022":raise ValueError("Metodologia censitária")
    with (ROOT/"POP-IBGE-MARICA-2014-2025.csv").open(newline="",encoding="utf-8") as f:
        csvrows=list(csv.DictReader(f))
    if [(int(r["ano"]),int(r["populacao_habitantes"]) if r["populacao_habitantes"] else None,r["tipo"],r["fonte"]) for r in csvrows]!=[(y,r["populacao_habitantes"],r["tipo"],r["fonte"]) for y,r in rows.items()]:
        raise ValueError("CSV e JSON divergentes")
    return rows

def compare(est,census,rows):
    if set(census)!={2022} or census[2022] is None:raise ValueError("Censo 2022 não confirmado")
    revisions=[]
    missing=[]
    for y,r in rows.items():
        if r["tipo"]=="estimativa_oficial_ibge_01_julho":
            if est.get(y) is None:missing.append(y)
            elif est[y]!=r["populacao_habitantes"]:revisions.append({"ano":y,"tipo":"estimativa","publicado":r["populacao_habitantes"],"oficial":est[y]})
    if census[2022]!=rows[2022]["populacao_habitantes"]:
        revisions.append({"ano":2022,"tipo":"censo","publicado":rows[2022]["populacao_habitantes"],"oficial":census[2022]})
    future=[{"ano":y,"populacao":v} for y,v in sorted(est.items()) if y>max(rows) and v is not None]
    # Eventual valor em 2023 requer identificação do produto IBGE, nunca imputação.
    exceptional=[{"ano":2023,"valor":est[2023]}] if est.get(2023) is not None else []
    return {"revisoes":revisions,"estimativas_ausentes_na_consulta":missing,"novos_anos":future,"ano_2023_revisar_produto":exceptional}

def main():
    rows=refs()
    result=compare(parse(fetch(EST),"9324"),parse(fetch(CENSO),"93"),rows)
    print("POP_IBGE_MONITOR",json.dumps(result,ensure_ascii=False),flush=True)
    if any(result.values()):
        raise SystemExit("Revisão coordenada de denominadores e indicadores dependentes necessária; sem publicação")
    print("POP_IBGE_OK: estimativas publicadas e Censo 2022 conferem; 2023 permanece nulo")
if __name__=="__main__":main()

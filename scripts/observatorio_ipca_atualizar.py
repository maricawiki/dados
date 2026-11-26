#!/usr/bin/env python3
"""IPCA oficial IBGE/SIDRA 1737 (variável 2266) para indicadores monetários.

Fonte pública: número-índice nacional, base dezembro de 1993 = 100.
Para fluxos anuais, usa MÉDIA ARITMÉTICA dos 12 números-índices de cada
exercício e do ano-base, não taxa anual acumulada e não índice de dezembro.
Não preenche competências ou anos incompletos com extrapolações.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import json
import re
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"observatorio/IPCA-IBGE-1737.json"
URL="https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/all?formato=json"
START=2000
LIMIT=2_000_000
THIRD=Decimal("0.000001")
def number(raw):
    val=str(raw).strip()
    if not val or val in ("...","..","-","X"):return None
    if "," in val and "." in val:val=val.replace(".","").replace(",",".")
    elif "," in val:val=val.replace(",",".")
    try:n=Decimal(val)
    except InvalidOperation:raise ValueError("IPCA com formato inesperado: "+val)
    if not n.is_finite() or n<=0 or n>=100000:raise ValueError("IPCA invalido: "+val)
    return n
def remote():
    err=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(URL,headers={
                "User-Agent":"Mozilla/5.0 MaricaWiki/Observatorio-IPCA (dados publicos)",
                "Accept":"application/json"
            })
            with urllib.request.urlopen(req,timeout=45) as r:
                if r.status!=200:raise ValueError("HTTP "+str(r.status))
                data=r.read(LIMIT+1)
            if len(data)>LIMIT:raise ValueError("Resposta IBGE excede 2MB")
            return json.loads(data.decode("utf-8-sig"))
        except Exception as exc:
            err=exc
            if attempt<2:time.sleep(attempt+1)
    raise RuntimeError("Falha ao consultar IBGE/SIDRA; base publicada preservada") from err
def build(rows):
    if not isinstance(rows,list) or len(rows)<100:
        raise ValueError("SIDRA sem serie suficiente")
    all_months={}
    for row in rows[1:]:
        # Na tabela 1737, D1=Brasil, D2=Variável e D3=Mês.
        if row.get("D2C")!="2266" or str(row.get("D1C")) not in ("1","Brasil"):
            raise ValueError("Esquema SIDRA inesperado: "+str(row)[:180])
        code=str(row.get("D3C",""))
        if not re.fullmatch(r"\d{6}",code):raise ValueError("Mês SIDRA inválido: "+code)
        year,month=int(code[:4]),int(code[4:])
        if not 1<=month<=12:raise ValueError("Mês inexistente: "+code)
        value=number(row.get("V"))
        if value is None:continue
        if code in all_months:raise ValueError("Duplicidade de competencia IBGE: "+code)
        all_months[code]=value
    included={k:v for k,v in all_months.items() if int(k[:4])>=START}
    if len(included)<(2025-START+1)*12:raise ValueError("IPCA 2000–2025 incompleto")
    last=max(included)
    expected=[f"{y}{m:02d}" for y in range(START,int(last[:4])+1) for m in range(1,13) if f"{y}{m:02d}"<=last]
    if sorted(included)!=expected:
        missing=set(expected)-set(included)
        raise ValueError("Competências IPCA ausentes: "+str(sorted(missing)[:12]))
    annual=[]
    for y in range(START,int(last[:4])+1):
        months=[included.get(f"{y}{m:02d}") for m in range(1,13)]
        valid=[p for p in months if p is not None]
        if len(valid)==12:
            mean=sum(valid)/Decimal(12)
            annual.append({"ano":y,"media_numero_indice":str(mean.quantize(THIRD,rounding=ROUND_HALF_UP)),"meses":12})
    if not annual or annual[-1]["ano"]<2025:raise ValueError("IPCA 2025 não está completo")
    return {
      "id":"IPCA-IBGE-1737",
      "titulo":"IPCA nacional, número-índice (dezembro de 1993 = 100)",
      "fonte":"IBGE/SIDRA - Tabela 1737, variável 2266, Brasil",
      "url_fonte":URL,
      "metodo":"Para fluxos anuais nominais: fator = média dos 12 números-índices do ano-base / média dos 12 números-índices do ano do valor.",
      "criterio_ano_base":"Último ano calendário com 12 competências oficiais completas; ano-base fixo opcional.",
      "nota":"Deflação aproximada de totais anuais uniformemente distribuídos; não equivale a deflação mensal do fluxo e não define PIB real.",
      "ano_base_automatico":annual[-1]["ano"],
      "ultima_competencia":last[:4]+"-"+last[4:],
      "medias_anuais":annual,
      "serie_mensal":[{"competencia":k[:4]+"-"+k[4:],"numero_indice":str(v)} for k,v in sorted(included.items())]
    }
def validate(data):
    assert data["id"]=="IPCA-IBGE-1737"
    months=data["serie_mensal"]
    assert len(months)>=(2025-START+1)*12
    assert months[0]["competencia"]==f"{START}-01", "Serie IPCA precisa iniciar em janeiro/2000"
    assert len({v["competencia"] for v in months})==len(months)
    assert all(months[i]["competencia"]<months[i+1]["competencia"] for i in range(len(months)-1)), "Competências fora de ordem"
    last=months[-1]["competencia"]
    expected=[f"{y}-{m:02d}" for y in range(START,int(last[:4])+1) for m in range(1,13) if f"{y}-{m:02d}"<=last]
    assert [m["competencia"] for m in months]==expected, "Lacuna no IPCA mensal entre 2000 e a última competência"
    assert data["ultima_competencia"]==last, "Última competência inconsistente"
    by_year=defaultdict(list)
    for row in months:
        by_year[int(row["competencia"][:4])].append(number(row["numero_indice"]))
    computed={}
    for y,vals in sorted(by_year.items()):
        if len(vals)==12:computed[y]=(sum(vals)/Decimal(12)).quantize(THIRD,rounding=ROUND_HALF_UP)
    published={v["ano"]:Decimal(v["media_numero_indice"]) for v in data["medias_anuais"]}
    assert published==computed, "Medias anuais nao batem com observacoes mensais"
    assert min(published)==START, "Ano 2000 não possui 12 meses completos"
    assert sorted(published)==list(range(START,max(published)+1)), "Ano IPCA completo ausente"
    assert data["ano_base_automatico"]==max(computed)
    assert max(computed)>=2025
    assert sorted(by_year)==list(range(START,max(by_year)+1))
    assert len(by_year[max(by_year)])<=12
    # Em um exercício completo, fator em relação ao mesmo ano é exatamente 1.
    for y,p in published.items():assert p/p==1
    return data
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--probe",action="store_true",help="consulta, valida e imprime JSON para revisão sem publicar")
    parser.add_argument("--atualizar",action="store_true",help="consulta, valida e atualiza cache oficial")
    parser.add_argument("--validar",action="store_true",help="somente verifica arquivo já publicado")
    args=parser.parse_args()
    if args.validar:
        if not TARGET.exists():raise SystemExit("Cache IPCA ainda não publicado")
        data=validate(json.loads(TARGET.read_text(encoding="utf-8")))
    elif args.probe or args.atualizar:
        data=validate(build(remote()))
        if args.atualizar:
            TARGET.parent.mkdir(parents=True,exist_ok=True)
            current=json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else None
            if current is not None and data["ultima_competencia"] < validate(current)["ultima_competencia"]:
                raise ValueError("Fonte retornou série mais curta; base anterior preservada")
            if current!=data:
                TARGET.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                print("IPCA_ALTERADO=sim",flush=True)
            else:print("IPCA_ALTERADO=nao",flush=True)
        if args.probe:print("IPCA_CACHE_JSON="+json.dumps(data,ensure_ascii=False,separators=(",",":")),flush=True)
    else:parser.error("Indique --probe, --atualizar ou --validar")
    print(f"IPCA_VALIDADO: base={data['ano_base_automatico']} meses={len(data['serie_mensal'])} ultima={data['ultima_competencia']}",flush=True)
if __name__=="__main__":main()

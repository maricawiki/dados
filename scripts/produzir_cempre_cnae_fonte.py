#!/usr/bin/env python3
"""ECO-005 (Produto 7, 4.2.7): empresas por seção CNAE, Maricá 2007–2024.

IBGE SIDRA CEMPRE 993 / 2585 (2007–2021), 9582 / 2585 (2022–2024).
NÃO equiparar a série setorial 9582 à tabela 9509 (empresas atuantes),
nem converter categorias com '-' em zeros. Fonte oficial, só dados observados.
"""
import csv
import io
import json
import os
import re
import string
import time
from decimal import Decimal,ROUND_HALF_UP
from html import escape
from pathlib import Path
from produzir_cempre import ROOT,ASSETS,get

CODE="ECO-005"
TITLE="Empresas por setor de atividade econômica (CNAE)"
SLUG="empresas-por-setor-cnae"
PERIODS={
    "historica_2007_2021":{
        "tabela":"993","variavel":"2585","anos":list(range(2007,2022)),
        "url":"https://apisidra.ibge.gov.br/values/t/993/n6/3302700/p/2007-2021/v/2585/c12762/all"
    },
    "nova_2022_2024":{
        "tabela":"9582","variavel":"2585","anos":[2022,2023,2024],
        "url":"https://apisidra.ibge.gov.br/values/t/9582/n6/3302700/p/2022-2024/v/2585/c12762/all"
    }
}
SECTIONS={
    "A":"116830","B":"116880","C":"116910","D":"117296","E":"117307",
    "F":"117329","G":"117363","H":"117484","I":"117543","J":"117555",
    "K":"117608","L":"117666","M":"117673","N":"117714","O":"117774",
    "P":"117788","Q":"117810","R":"117838","S":"117861","T":"117888",
    "U":"117892",
}
CENT=Decimal("0.000001")

def parse():
    result={}
    labels={}
    for regime,p in PERIODS.items():
        source=get(p["url"])
        expected=p["anos"]
        if len(source)!=len(expected)*22:
            raise ValueError(f"{regime}: esperado {len(expected)*22} registros, recebido {len(source)}")
        matrix={}
        for r in source:
            if (r.get("NC")!="6" or r.get("MC")!="1020" or r.get("D1C")!="3302700"
                or r.get("D3C")!=p["variavel"] or r.get("D5C")!="0" or r.get("D6C")!="0"):
                raise ValueError(f"Identificadores inesperados em {regime}: {r}")
            y=int(r["D2C"])
            if y not in expected:raise ValueError(f"Exercício inesperado: {y}")
            category=str(r["D4C"])
            if category=="0":
                key="total"
                if r.get("D4N")!="Total":raise ValueError("Conta total sem rótulo")
            else:
                label=r.get("D4N","")
                if not re.match(r"^[A-U] ",label):
                    raise ValueError(f"Seção CNAE não reconhecida: {label}")
                key=label[0]
                if SECTIONS[key]!=category:raise ValueError(f"Código CNAE mudou: {key}/{category}")
                if key in labels and labels[key]!=label:raise ValueError(f"Nome da seção mudou: {key}")
                labels[key]=label
            raw=str(r.get("V",""))
            if raw.isdigit():value=int(raw)
            elif raw in ("-","...","..","X","x"):value=None
            else:raise ValueError(f"Valor desconhecido {raw} no exercício {y}, seção {key}")
            if key=="total" and (value is None or value<=0):
                raise ValueError(f"Total inválido {y}")
            d=matrix.setdefault(y,{})
            if key in d:raise ValueError(f"Duplicidade em {y}, seção {key}")
            d[key]=value
        if sorted(matrix)!=expected:raise ValueError(f"Faltam anos em {regime}")
        for y in expected:
            d=matrix[y]
            if set(d)!=set(SECTIONS)|{"total"}:raise ValueError(f"Seções faltantes em {y}")
            total=d["total"]
            sector_sum=sum(v for k,v in d.items() if k!="total" and v is not None)
            if sector_sum>total:raise ValueError(f"Soma setorial excede total em {y}: {sector_sum}>{total}")
            remainder=total-sector_sum
            result[y]={
                "ano":y,"regime":regime,"tabela_sidra":p["tabela"],
                "variavel_sidra":p["variavel"],"url_fonte":p["url"],
                "total_empresas":total,"soma_setores_informados":sector_sum,
                "nao_distribuido":remainder,
                "setores":[{
                    "secao":k,"codigo_categoria":SECTIONS[k],"nome":labels[k],
                    "valor":d[k],
                    "participacao_total_pct":str(
                        (Decimal(d[k])/Decimal(total)*100).quantize(CENT,rounding=ROUND_HALF_UP))
                        if d[k] is not None else None,
                    "status":"informado" if d[k] is not None else "nao_informado"
                } for k in string.ascii_uppercase[:21]]
            }
            print("ECO_CEMPRE_CNAE",json.dumps({
                "ano":y,"tabela":p["tabela"],"total":total,
                "soma_setores":sector_sum,"residuo":remainder,
                "nao_informados":[k for k in SECTIONS if d[k] is None]
            },ensure_ascii=False),flush=True)
        time.sleep(1.1)
    if sorted(result)!=list(range(2007,2025)) or len(labels)!=21:
        raise ValueError("Cobertura 2007–2024 e 21 seções não confirmadas")
    if result[2021]["total_empresas"]!=2890 or result[2022]["total_empresas"]!=4884 or result[2024]["total_empresas"]!=5736:
        raise ValueError("Âncoras oficiais SIDRA 993/9582 não coincidem")
    # Nunca conciliar valores de 9582 aos da 9509; universos não idênticos.
    eco3=json.loads((ASSETS/"ECO-003.json").read_text(encoding="utf-8"))
    eco3_by_year={x["ano"]:x["valor"] for x in eco3["serie"]}
    for y in range(2007,2022):
        if eco3_by_year[y]!=result[y]["total_empresas"]:
            raise ValueError(f"Histórico CNAE diverge do ECO-003 em {y}")
    if result[2024]["total_empresas"]==eco3_by_year[2024]:
        raise ValueError("Relação entre tabelas 9582 e 9509 mudou; revisar conceitos")
    for y in (2022,2023,2024):
        result[y]["total_eco003_9509"] = eco3_by_year[y]
        result[y]["diferenca_9509_menos_9582"]=eco3_by_year[y]-result[y]["total_empresas"]
    return [result[y] for y in sorted(result)],labels

def csvdata(serie):
    out=io.StringIO(newline="")
    w=csv.writer(out,delimiter=";",lineterminator="\n")
    w.writerow(["ano","regime","tabela_sidra","secao","codigo_categoria","nome",
       "valor","participacao_total_pct","status","total_empresas_tabela","nao_distribuido","fonte"])
    for y in serie:
        for x in y["setores"]:
            w.writerow([y["ano"],y["regime"],y["tabela_sidra"],x["secao"],x["codigo_categoria"],
                x["nome"],x["valor"] if x["valor"] is not None else "",
                x["participacao_total_pct"] or "",x["status"],y["total_empresas"],
                y["nao_distribuido"],y["url_fonte"]])
    return out.getvalue()


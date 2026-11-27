#!/usr/bin/env python3
"""FIN-015/016/017: per capita da DCA com denominadores IBGE históricos auditados.

Não usa interpolações, projeções próprias, população de 2022 como estimativa de
2023 nem converte receita bruta em líquida. Em 2023, apenas o numerador é
publicado: não houve estimativa municipal anual do IBGE naquele exercício.
"""
import csv
import io
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path

from produzir_dca import ROOT, ASSETS, YEARS

def load_population():
    reference=json.loads((ASSETS/"POP-IBGE-MARICA-2014-2025.json").read_text(encoding="utf-8"))
    subset=json.loads((ASSETS/"FIN-POP-IBGE-2019-2025.json").read_text(encoding="utf-8"))
    if subset["codigo_ibge"]!="3302700":raise ValueError("Denominador territorial incorreto")
    primary={x["ano"]:x for x in reference["serie"]}
    pop={}
    for row in subset["serie"]:
        year=row["ano"]
        if year in pop or year not in primary:raise ValueError("Denominador duplicado ou ausente")
        if any(row[key]!=primary[year][key] for key in ("populacao_habitantes","tipo")):
            raise ValueError("Denominador fiscal diverge da base IBGE consolidada")
        p=row["populacao_habitantes"]
        if p is not None and (type(p) is not int or p<=0):raise ValueError("População inválida")
        pop[year]=(p,row["tipo"],row["fonte"])
    return pop

SPECS={
  "FIN-015":("Receita orçamentária per capita","receita-orcamentaria-per-capita",
             "6.1.2","FIN-001","receita_bruta_realizada_reais",
             "Receita orçamentária BRUTA realizada no exercício, dividida pela população oficial de referência do IBGE."),
  "FIN-016":("Arrecadação tributária per capita","arrecadacao-tributaria-per-capita",
             "6.1.3","FIN-008","valor",
             "Impostos, taxas e contribuições de melhoria arrecadados no exercício, divididos pela população oficial de referência do IBGE."),
  "FIN-017":("Investimentos liquidados per capita","investimentos-liquidados-per-capita",
             "6.2.7","FIN-006","despesa_liquidada_reais",
             "Despesas liquidadas de investimentos (grupo 4.4), divididas pela população oficial de referência do IBGE."),
}
CENT=Decimal("0.01")
def number(v):
    d=Decimal(str(v))
    if not d.is_finite() or d<=0:
        raise ValueError(f"Numerador contábil inválido: {v}")
    return d.quantize(CENT)

def load_amounts(code,field):
    meta=json.loads((ASSETS/(code+".json")).read_text(encoding="utf-8"))
    assert meta["id"]==code and meta["codigo_ibge"]=="3302700"
    rows=meta["serie"]
    if [x["ano"] for x in rows]!=YEARS:
        raise ValueError(f"{code}: ano ausente ou ordem alterada")
    result={r["ano"]:number(r[field]) for r in rows}
    if len(result)!=7:raise ValueError("Numerador com anos repetidos")
    return result,meta

def extract():
    POP=load_population()
    if sorted(POP)!=YEARS:
        raise ValueError("Denominadores IBGE sem exercício identificado")
    if sum(p is not None for p,_,_ in POP.values())!=6:
        raise ValueError("Denominadores não podem ser interpolados")
    if POP[2023][0] is not None or POP[2022][1]!="censo_demografico_2022":
        raise ValueError("2022 e 2023 não podem ser tratados como estimativa anual homogênea")
    data={}
    for code,(_,_,ref,source,field,_) in SPECS.items():
        numerators,original=load_amounts(source,field)
        rows=[]
        for year in YEARS:
            population,pop_type,pop_url=POP[year]
            amount=numerators[year]
            per=(amount/Decimal(population)).quantize(CENT,rounding=ROUND_HALF_UP) if population else None
            rows.append({
                "ano":year,"valor":str(per) if per is not None else None,
                "numerador_reais":str(amount),
                "populacao_habitantes":population,
                "tipo_populacao":pop_type,
                "fonte_populacao":pop_url,
                "status":"calculado_com_denominador_oficial" if population else "sem_denominador_anual_oficial",
            })
            print("FIN_PER_CAPITA",json.dumps({
                "codigo":code,"ano":year,"numerador":str(amount),
                "populacao":population,"tipo":pop_type,
                "valor_per_capita":str(per) if per is not None else None
            },ensure_ascii=False),flush=True)
        data[code]=rows
    return data

def csv_file(rows):
    output=io.StringIO(newline="")
    writer=csv.writer(output,delimiter=";",lineterminator="\n")
    writer.writerow(("ano","valor_per_capita_reais","numerador_reais","populacao_habitantes",
                     "tipo_populacao","status","fonte_populacao"))
    for x in rows:
        writer.writerow((x["ano"],x["valor"] if x["valor"] is not None else "",
                        x["numerador_reais"],x["populacao_habitantes"] or "",
                        x["tipo_populacao"],x["status"],x["fonte_populacao"]))
    return output.getvalue()


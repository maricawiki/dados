#!/usr/bin/env python3
"""Adiciona três recortes anuais conferidos do estoque RAIS 2014–2025 de Maricá.

Fonte: índice RAIS/MTE do painel ONMT, espelho independente de SHA fixo;
a fonte primária RAIS 2025 (Tabela 4) confere os totais 2023–2025.
Todos os 12 anos devem ter o mesmo universo, com somas categóricas exatas.
Correspondências com o Produto 7 de 2022 permanecem PARCIAIS.
"""
import csv
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from rais_vinculos_base import YEARS,OFFICIAL_STOCK,integer,retrieve,normalize
SPECS={
 "TRB-032":("Empregos formais por subgrupo de atividade econômica",
            "empregos-formais-subgrupo-atividade","5.2.4","subgrupo",
            "Subgrupos de atividade do painel MTE não têm equivalência automaticamente certificada com os subsetores originais RAIS de 2022."),
 "TRB-034":("Empregos formais por faixa de renda",
            "empregos-formais-faixa-renda","5.2.10","renda",
            "O painel apresenta quatro faixas em salários mínimos; a correspondência com outras classificações exige verificação."),
 "TRB-035":("Empregos formais por horas contratuais",
            "empregos-formais-horas-contratuais","5.2.11","horas",
            "Faixas de horas contratuais do painel MTE; a comparação com outras bases exige verificar a definição de cada classe."),
}

def cut(row,kind):
    y,t1,a1,t2,a2,v=row
    table={
      "subgrupo":"Subgrupo de atividade","renda":"Faixa de renda",
      "horas":"Horas trabalhadas"
    }
    if kind in table:
        if t1!="Total" or t2!=table[kind] or a1 not in (None,"","Total") or a2 in (None,"","Total"):
            return None
        return str(a2)
    raise ValueError("Recorte não registrado")

def collect(cache=None):
    import duckdb
    source,temp=retrieve(cache)
    try:
        db=duckdb.connect()
        rows=db.execute("""
           SELECT period,"tipo_abertura.1","abertura.1",
                  "tipo_abertura.2","abertura.2",valor
           FROM read_parquet(?)
           WHERE codigo_ibge='330270' AND variaveis='abs_rais_emp_formal'
             AND period BETWEEN 2014 AND 2025 AND valor IS NOT NULL
        """,[str(source)]).fetchall()
    finally:
        if temp:
            source.unlink(missing_ok=True)
            source.parent.rmdir()
    totals={}
    for y,t1,a1,t2,a2,v in rows:
        if t1=="Total" and t2=="Total":
            if int(y) in totals:raise ValueError("RAIS total repetido")
            totals[int(y)]=integer(v)
    if sorted(totals)!=YEARS or {y:totals[y] for y in OFFICIAL_STOCK}!=OFFICIAL_STOCK:
        raise ValueError(f"Estoque total inconsistente com RAIS MTE 2025: {totals}")
    # Esses três recortes apresentam cobertura integral em todos os 12 anos.
    # Porte de empresa não cobre todo o estoque; cruzamentos sexo × atividade
    # não estão disponibilizados na fonte consultada. Não imputar valores.
    cuts={}
    for kind in ("subgrupo","renda","horas"):
        yearly={}
        for year in YEARS:
            recs={}
            for row in rows:
                if int(row[0])!=year:continue
                name=cut(row,kind)
                if name is None:continue
                if name in recs:
                    raise ValueError(f"Categoria duplicada: {year}, {kind}, {name}")
                recs[name]=integer(row[-1])
            if len(recs)<2 or sum(recs.values())!=totals[year]:
                raise ValueError(
                    f"Subtotais RAIS não conciliam: {year}, {kind}, "
                    f"{len(recs)} categorias, {sum(recs.values())}/{totals[year]}"
                )
            yearly[year]=recs
        cuts[kind]=yearly
    result={}
    for code,(title,slug,prod,kind,note) in SPECS.items():
        series=[{"ano":y,"total":totals[y],
                 "categorias":[{"categoria":k,"vinculos":v}
                    for k,v in sorted(cuts[kind][y].items(),key=lambda x:normalize(x[0]))]}
                for y in YEARS]
        result[code]=series
        print("RAIS_RECORTE",code,prod,
              "CATEGORIAS",len(series[-1]["categorias"]),
              "ANOS",len(series),"TOTAL_2025",series[-1]["total"],
              "AMOSTRA_2025",series[-1]["categorias"][:6],flush=True)
    return result


#!/usr/bin/env python3
"""Três séries DCA para Maricá: royalties (6.1.7/6.1.8) e dívida (6.2.8).

O universo é o das rubricas EXPRESSAMENTE identificadas de royalties e
participação especial, não todas as compensações pela exploração de recursos.
Nunca utilizar conta-mãe somada com filhas, FEP ou outras compensações genéricas.
"""
import csv
import io
import json
import os
import re
import time
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path

from observatorio_financas_siconfi_sondar import get_dca
from produzir_dca import ROOT, ASSETS, YEARS, REVENUE_COL, EXPENSE_COL, money, baseline

SPECS={
    "FIN-012":("Royalties e participações especiais identificados",
               "royalties-participacoes-especiais","6.1.7","petroleo",
               "Soma de rubricas explicitamente identificadas de royalties federais, participação especial e royalties estaduais. Não equivale ao conjunto das compensações financeiras por recursos naturais."),
    "FIN-013":("Participação de royalties e participações especiais na receita bruta",
               "participacao-royalties-receita","6.1.8","percentual",
               "Razão entre as rubricas de petróleo identificadas no FIN-012 e a receita orçamentária BRUTA realizada (FIN-001), multiplicada por 100."),
    "FIN-014":("Despesas com dívida pública liquidadas",
               "despesas-divida-publica","6.2.8","divida",
               "Soma dos grupos de natureza 3.2 (juros e encargos da dívida) e 4.6 (amortização da dívida), na coluna Despesas Liquidadas da DCA I-D."),
}
OLD={
 "royal_uniao_lei": "RO1.7.1.8.02.3.0",
 "royal_uniao_excedente": "RO1.7.1.8.02.4.0",
 "participacao_especial": "RO1.7.1.8.02.5.0",
 "royal_estado": "RO1.7.2.8.02.3.0",
}
NEW={
 "royal_uniao_lei": "RO1.7.1.2.52.1.0",
 "royal_uniao_excedente": "RO1.7.1.2.52.2.0",
 "participacao_especial": "RO1.7.1.2.52.3.0",
 "royal_estado": "RO1.7.2.2.52.0.0",
}
GROUP_DEBT={"juros":"DO3.2.00.00.00.00","amortizacao":"DO4.6.00.00.00.00"}
PERCENT=Decimal("0.000001")

def exact(rows, code, col, optional=False):
    hits=[r for r in rows if str(r.get("cod_conta"))==code
          and r.get("coluna")==col and r.get("rotulo")=="Padrão"]
    if len(hits)==0 and optional:
        return None
    if len(hits)!=1:
        raise ValueError(f"{code}/{col}: {len(hits)} contas; esperada uma")
    result=money(hits[0]["valor"])
    if result<0:
        raise ValueError(f"Valor negativo inesperado para {code}")
    return result

def extract():
    total_revenue=baseline("FIN-001","receita_bruta_realizada_reais")
    total_expense=baseline("FIN-002","despesas_liquidadas_reais")
    transfers={int(x["ano"]):money(x["valor"]) for x in
               json.loads((ASSETS/"FIN-009.json").read_text(encoding="utf-8"))["serie"]}
    data={code:[] for code in SPECS}
    for y in YEARS:
        ic=get_dca(y,"DCA-Anexo I-C")
        time.sleep(1.15)
        idata=get_dca(y,"DCA-Anexo I-D")
        time.sleep(1.15)
        if exact(ic,"TotalReceitas",REVENUE_COL)!=total_revenue[y]:
            raise ValueError(f"Receita de {y} não coincide com FIN-001")
        if exact(idata,"TotalDespesas",EXPENSE_COL)!=total_expense[y]:
            raise ValueError(f"Despesa de {y} não coincide com FIN-002")
        codes=OLD if y<=2021 else NEW
        vals={k:exact(ic,v,REVENUE_COL,optional=(k=="royal_estado" and y==2022))
              for k,v in codes.items()}
        if any(vals[k] is None for k in ("royal_uniao_lei","royal_uniao_excedente","participacao_especial")):
            raise ValueError(f"Rubricas federais não localizadas em {y}")
        federal_royalties=vals["royal_uniao_lei"]+vals["royal_uniao_excedente"]
        special=vals["participacao_especial"]
        state=vals["royal_estado"]
        federal_total=federal_royalties+special
        identified=federal_total+(state if state is not None else Decimal(0))
        if y<=2021:
            parent=exact(ic,"RO1.7.1.8.02.0.0",REVENUE_COL)
            generic_code="RO1.7.1.8.02.9.0"
        else:
            parent=exact(ic,"RO1.7.1.2.52.0.0",REVENUE_COL)
            generic_code="RO1.7.1.2.99.0.0"
        if not (0<federal_total<=parent and 0<identified<=transfers[y]<total_revenue[y]):
            raise ValueError(f"Subcontas de royalties sem conciliação em {y}")
        generic=exact(ic,generic_code,REVENUE_COL,optional=True)
        # O rótulo 'Outras compensações' NÃO prova que os ingressos sejam petróleo.
        row={"ano":y,"valor":str(identified),
             "royalties_uniao":str(federal_royalties),
             "participacao_especial":str(special),
             "royalties_estado":str(state) if state is not None else None,
             "estadual_sem_rubrica":state is None,
             "outras_compensacoes_nao_incluidas":str(generic) if generic is not None else None,
             "codigos_usados":[codes[k] for k in ("royal_uniao_lei","royal_uniao_excedente",
                                                   "participacao_especial")]+([codes["royal_estado"]] if state is not None else [])}
        ratio=(identified/total_revenue[y]*100).quantize(PERCENT,rounding=ROUND_HALF_UP)
        data["FIN-012"].append(row)
        data["FIN-013"].append({"ano":y,"valor":str(ratio),
                                "receitas_identificadas":str(identified),
                                "receita_bruta":str(total_revenue[y]),
                                "estadual_sem_rubrica":state is None})
        juros=exact(idata,GROUP_DEBT["juros"],EXPENSE_COL)
        amort=exact(idata,GROUP_DEBT["amortizacao"],EXPENSE_COL)
        divida=juros+amort
        if divida<=0 or divida>=total_expense[y]:
            raise ValueError(f"Despesa da dívida inválida em {y}")
        data["FIN-014"].append({"ano":y,"valor":str(divida),
                                "juros_encargos":str(juros),"amortizacao":str(amort)})
        print("DCA_PETROLEO_DIVIDA_CONCILIADA",json.dumps({
            "ano":y,"royalties_identificados":str(identified),
            "part_percentual":str(ratio),"royalties_estado_declarado":state is not None,
            "outras_compensacoes_nao_incluidas":str(generic) if generic is not None else None,
            "juros":str(juros),"amortizacao":str(amort),"divida_liquidada":str(divida)
        },ensure_ascii=False),flush=True)
    return data

def csv_data(series,kind):
    f=io.StringIO(newline="")
    out=csv.writer(f,delimiter=";",lineterminator="\n")
    if kind=="petroleo":
        keys=("ano","valor","royalties_uniao","participacao_especial",
              "royalties_estado","estadual_sem_rubrica","outras_compensacoes_nao_incluidas")
    elif kind=="percentual":
        keys=("ano","valor","receitas_identificadas","receita_bruta","estadual_sem_rubrica")
    else:
        keys=("ano","valor","juros_encargos","amortizacao")
    out.writerow(keys)
    for x in series:
        out.writerow([x.get(k) if x.get(k) is not None else "" for k in keys])
    return f.getvalue()


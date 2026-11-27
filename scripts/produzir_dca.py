#!/usr/bin/env python3
"""Integra quatro indicadores DCA 2019–2025 de Maricá após conciliação.

FIN-008/009/010: receitas e transferências correntes.
FIN-011: despesa liquidada por função.
Jamais somar funções a subfunções ou receitas sintéticas às analíticas.
Os totais são conferidos com FIN-001 e FIN-002 sem edição de fichas.
"""
import argparse
import csv
import io
import json
import os
import re
import time
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path

from observatorio_financas_siconfi_sondar import get_dca

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"observatorio"
YEARS=list(range(2019,2026))
CENT=Decimal("0.01")
REVENUE_COL="Receitas Brutas Realizadas"
EXPENSE_COL="Despesas Liquidadas"
SPECS={
 "FIN-008":("Receita tributária própria","receita-tributaria-propria","6.1.4","reais",
            "Receita tributária arrecadada: impostos, taxas e contribuições de melhoria (conta 1.1), sem somar transferências ou contribuições especiais."),
 "FIN-009":("Transferências correntes da União e do Estado","transferencias-uniao-estado","6.1.5","reais",
            "Soma das transferências correntes da União e de suas entidades (1.7.1) e dos Estados e do DF (1.7.2). Não inclui transferências de capital nem transferências privadas."),
 "FIN-010":("Participação das transferências correntes na receita total","transferencias-participacao","6.1.6","percentual",
            "Transferências correntes da União e dos Estados divididas pela receita orçamentária BRUTA realizada (FIN-001), multiplicadas por 100."),
 "FIN-011":("Despesas liquidadas por função de governo","despesas-funcao-governo",None,"funcoes",
            "DCA Anexo I-E, despesas liquidadas EXCETO intraorçamentárias, discriminadas apenas por função (dois dígitos), sem somar subfunções. O total de funções somado à parcela intra é conciliado com FIN-002."),
}

def money(value):
    if value is None:raise ValueError("Valor financeiro ausente")
    v=Decimal(str(value))
    if not v.is_finite():raise ValueError("Valor financeiro não finito")
    if abs(v-v.quantize(CENT))>Decimal("0.000001"):
        raise ValueError("Conta com casas decimais além de centavos: "+str(v))
    return v.quantize(CENT)

def key(row):
    return str(row.get("cod_conta","")).strip()

def select(rows,code,col,rotulo):
    match=[x for x in rows if key(x)==code and x.get("coluna")==col and x.get("rotulo")==rotulo]
    if len(match)!=1:raise ValueError(f"Conta {code}/{col}/{rotulo}: {len(match)} registros")
    return money(match[0].get("valor"))

def baseline(code,field):
    with (ASSETS/(code+".csv")).open(encoding="utf-8",newline="") as fh:
        rows=list(csv.DictReader(fh))
    if [int(x["ano"]) for x in rows]!=YEARS:raise ValueError(f"Série original {code} alterada ou incompleta")
    return {int(x["ano"]):money(x[field]) for x in rows}

def extract():
    revenues=baseline("FIN-001","receita_bruta_realizada_reais")
    expenses=baseline("FIN-002","despesas_liquidadas_reais")
    data={code:[] for code in SPECS}
    for y in YEARS:
        ic=get_dca(y,"DCA-Anexo I-C")
        time.sleep(1.2)
        ie=get_dca(y,"DCA-Anexo I-E")
        time.sleep(1.2)
        receita=select(ic,"TotalReceitas",REVENUE_COL,"Padrão")
        if receita!=revenues[y]:raise ValueError(f"Receita DCA divergente do FIN-001 em {y}: {receita}/{revenues[y]}")
        trib=select(ic,"RO1.1.0.0.00.0.0",REVENUE_COL,"Padrão")
        uniao=select(ic,"RO1.7.1.0.00.0.0",REVENUE_COL,"Padrão")
        estado=select(ic,"RO1.7.2.0.00.0.0",REVENUE_COL,"Padrão")
        transferencias=uniao+estado
        correntes=select(ic,"RO1.7.0.0.00.0.0",REVENUE_COL,"Padrão")
        if not (0<trib<receita and 0<transferencias<=correntes<receita):
            raise ValueError(f"Receitas sem integridade em {y}")
        share=(Decimal(100)*transferencias/receita).quantize(Decimal("0.000001"),rounding=ROUND_HALF_UP)
        data["FIN-008"].append({"ano":y,"valor":str(trib)})
        data["FIN-009"].append({"ano":y,"valor":str(transferencias),"uniao":str(uniao),"estado":str(estado)})
        data["FIN-010"].append({"ano":y,"valor":str(share),"receita_bruta":str(receita),"transferencias":str(transferencias)})

        frows=[r for r in ie if key(r)=="TotalDespesas" and r.get("coluna")==EXPENSE_COL
               and r.get("rotulo")=="Total Geral da Despesa por Função"]
        excl=[r for r in frows if r.get("conta")=="Despesas Exceto Intraorçamentárias"]
        intra=[r for r in frows if r.get("conta")=="Despesas Intraorçamentárias"]
        if len(excl)!=1 or len(intra)!=1:raise ValueError(f"Totais por função inesperados em {y}")
        exc=money(excl[0]["valor"]); intr=money(intra[0]["valor"])
        if exc+intr!=expenses[y]:
            raise ValueError(f"Anexo I-E não concilia com I-D em {y}: {exc}+{intr}!={expenses[y]}")
        functions=[]
        for r in frows:
            m=re.fullmatch(r"(\d{2}) - (.+)",str(r.get("conta","")).strip())
            if m:
                functions.append({"codigo":m.group(1),"nome":m.group(2),
                                  "valor":str(money(r["valor"]))})
        if len(functions)<15 or len({x["codigo"] for x in functions})!=len(functions):
            raise ValueError(f"Funções inválidas/duplicadas em {y}")
        functions.sort(key=lambda x:x["codigo"])
        if sum((Decimal(f["valor"]) for f in functions),Decimal(0))!=exc:
            raise ValueError(f"Soma das funções não coincide com despesa exceto intra em {y}")
        data["FIN-011"].append({"ano":y,"valor":str(exc),"intra":str(intr),
                                "total":str(expenses[y]),"funcoes":functions})
        print("FIN_DCA_AUDITORIA",y,"RECEITA",receita,"TRIBUTARIA",trib,
              "TRANSFERENCIA",transferencias,"PERCENTUAL",share,
              "DESPESA_EXCETO_INTRA",exc,"INTRA",intr,
              "FUNCOES",len(functions),flush=True)
    return data

def csv_file(data,kind):
    output=io.StringIO(newline="")
    csvout=csv.writer(output,delimiter=";",lineterminator="\n")
    if kind=="funcoes":
        csvout.writerow(["ano","codigo_funcao","funcao","despesas_liquidadas_reais",
                         "despesa_total_exceto_intra_reais","despesa_intra_reais",
                         "despesa_total_reais"])
        for x in data:
            for f in x["funcoes"]:
                csvout.writerow([x["ano"],f["codigo"],f["nome"],f["valor"],x["valor"],x["intra"],x["total"]])
    elif kind=="percentual":
        csvout.writerow(["ano","participacao_percentual","transferencias_correntes_reais","receita_bruta_realizada_reais"])
        for x in data:csvout.writerow([x["ano"],x["valor"],x["transferencias"],x["receita_bruta"]])
    elif kind=="reais" and "uniao" in data[0]:
        csvout.writerow(["ano","transferencias_correntes_total_reais","transferencias_uniao_reais","transferencias_estado_reais"])
        for x in data:csvout.writerow([x["ano"],x["valor"],x["uniao"],x["estado"]])
    else:
        csvout.writerow(["ano","receita_tributaria_propria_reais"])
        for x in data:csvout.writerow([x["ano"],x["valor"]])
    return output.getvalue()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--propor",type=Path)
    args=parser.parse_args()
    data=extract()
    changed=[]
    candidate={}
    for code,rows in data.items():
        old=json.loads((ASSETS/(code+".json")).read_text(encoding="utf-8"))
        if old["id"]!=code or old["codigo_ibge"]!="3302700":
            raise ValueError("Identidade do indicador inválida")
        raw=csv_file(rows,SPECS[code][3])
        if rows!=old["serie"] or raw!=(ASSETS/(code+".csv")).read_bytes().decode("utf-8"):
            changed.append(code)
            old["serie"]=rows
            if os.environ.get("GITHUB_RUN_ID"):
                old["fonte"]["consulta_execucao"]="https://github.com/maricawiki/dados/actions/runs/"+os.environ["GITHUB_RUN_ID"]
        candidate[code+".json"]=json.dumps(old,ensure_ascii=False,indent=2)+"\n"
        candidate[code+".csv"]=raw
    if args.propor:
        out=args.propor.resolve()
        if out==ROOT or ROOT in out.parents:
            raise ValueError("Propostas somente fora do repositório")
        out.mkdir(parents=True,exist_ok=False)
        for name,content in candidate.items():
            (out/name).write_text(content,encoding="utf-8")
    if changed:
        raise SystemExit("DCA_REVISAR: "+", ".join(changed))
    print("DCA_OK: FIN-008 a FIN-011 conciliados com FIN-001/002; 2019–2025",flush=True)

if __name__=="__main__":
    main()

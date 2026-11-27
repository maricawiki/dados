#!/usr/bin/env python3
"""CEMPRE: produtor de agregados ECO-003/004, 2007–2024, sem edição do portal.

ECO-003: número de empresas e outras organizações atuantes (Produto 7 4.2.1).
ECO-004: taxa de variação anual dentro da mesma metodologia (4.2.4).
Fontes: IBGE SIDRA tabela 993/v2585 (2007–2021) e 9509/v367 (2022–2024).
"""
import argparse
import csv
import io
import json
import os
import time
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"observatorio"
YEARS=list(range(2007,2025))
ENDPOINTS={
    "historica_2007_2021":"https://apisidra.ibge.gov.br/values/t/993/n6/3302700/p/2007-2021/v/2585",
    "nova_2022_2024":"https://apisidra.ibge.gov.br/values/t/9509/n6/3302700/p/2022-2024/v/367",
}
SPECS={
    "ECO-003":("Número de empresas e outras organizações (CEMPRE)",
               "empresas-cempre","4.2.1","empresas",
               "Quantidade de empresas e outras organizações formais atuantes em Maricá, conforme o Cadastro Central de Empresas (CEMPRE) do IBGE."),
    "ECO-004":("Variação anual do número de empresas (CEMPRE)",
               "variacao-empresas-cempre","4.2.4","variacao",
               "Variação percentual anual do número de empresas e outras organizações, calculada apenas entre exercícios da mesma série metodológica do CEMPRE."),
}
PERCENT=Decimal("0.000001")
def get(source):
    if urlparse(source).hostname!="apisidra.ibge.gov.br":
        raise ValueError("Fonte SIDRA não oficial")
    req=Request(source,headers={"Accept":"application/json","User-Agent":"MaricaWiki-Cempre/1.0"})
    with urlopen(req,timeout=35) as resp:
        j=json.load(resp)
    if not isinstance(j,list) or len(j)<2 or not all(isinstance(r,dict) for r in j):
        raise ValueError("SIDRA não retornou série completa")
    return j[1:]

def extract():
    all_rows={}
    for regime,url in ENDPOINTS.items():
        table="993" if regime.startswith("historica") else "9509"
        var="2585" if table=="993" else "367"
        expected=list(range(2007,2022)) if table=="993" else [2022,2023,2024]
        source=get(url)
        if len(source)!=len(expected):
            raise ValueError(f"{regime}: esperados {len(expected)} anos, obtidos {len(source)}")
        for x in source:
            year=int(x.get("D2C","0"))
            if year not in expected or year in all_rows:
                raise ValueError(f"Ano inesperado/duplicado no SIDRA: {year}")
            if (x.get("D1C")!="3302700" or x.get("D3C")!=var or
                x.get("NC")!="6" or x.get("MC")!="1020" or
                "empresas e outras organizações" not in x.get("D3N","").lower()):
                raise ValueError(f"Conceito ou município inesperado: {x}")
            if table=="993" and any(x.get(k)!="0" for k in ("D4C","D5C","D6C")):
                raise ValueError("Série 993 contém subgrupo não total")
            value=x.get("V","")
            if not str(value).isdigit() or int(value)<=0:
                raise ValueError(f"Valor empresarial faltante ou inválido em {year}: {value}")
            all_rows[year]={"ano":year,"valor":int(value),"regime":regime,
                            "tabela_sidra":table,"variavel_sidra":var,
                            "fonte":url}
        time.sleep(1.15)
    if sorted(all_rows)!=YEARS:
        raise ValueError("Falta observação anual ou há excesso de registros")
    if all_rows[2007]["valor"]!=1753 or all_rows[2019]["valor"]!=2297 or all_rows[2021]["valor"]!=2890:
        raise ValueError("Âncoras históricas 993 alteradas")
    if [all_rows[y]["valor"] for y in (2022,2023,2024)]!=[5179,5647,6108]:
        raise ValueError("Âncoras nova série 9509 alteradas")
    empresas=[all_rows[y] for y in YEARS]
    variacao=[]
    for x in empresas:
        y=x["ano"]
        prior=all_rows.get(y-1)
        valid=bool(prior and prior["regime"]==x["regime"])
        value=((Decimal(x["valor"]-prior["valor"])/Decimal(prior["valor"]))*100).quantize(
                PERCENT,rounding=ROUND_HALF_UP) if valid else None
        status=("sem_ano_anterior_na_serie" if y==2007 else
                "quebra_metodologica_cempre_2022" if y==2022 else "calculado")
        variacao.append({
            "ano":y,"valor":str(value) if valid else None,"status":status,
            "empresas_ano":x["valor"],"empresas_ano_anterior":prior["valor"] if valid else None,
            "regime":x["regime"],"tabela_sidra":x["tabela_sidra"],
        })
    assert variacao[0]["valor"] is None and variacao[15]["valor"] is None
    assert sum(x["valor"] is not None for x in variacao)==16
    assert all(x["valor"] is not None for x in variacao[1:15]+variacao[16:])
    for x in empresas:
        print("ECO_CEMPRE_OFICIAL",json.dumps({
            "ano":x["ano"],"empresas":x["valor"],"tabela":x["tabela_sidra"],
            "variacao":next(v["valor"] for v in variacao if v["ano"]==x["ano"])
        },ensure_ascii=False),flush=True)
    return {"ECO-003":empresas,"ECO-004":variacao}

def to_csv(rows,kind):
    buf=io.StringIO(newline="")
    w=csv.writer(buf,delimiter=";",lineterminator="\n")
    if kind=="empresas":
        fields=["ano","valor","regime","tabela_sidra","variavel_sidra","fonte"]
    else:
        fields=["ano","valor","status","empresas_ano","empresas_ano_anterior","regime","tabela_sidra"]
    w.writerow(fields)
    for x in rows:w.writerow([x.get(k) if x.get(k) is not None else "" for k in fields])
    return buf.getvalue()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--propor",type=Path,help="Diretório novo, fora da árvore versionada")
    args=parser.parse_args()
    data=extract()
    # Descoberta de novas referências sem alterar os regimes nem as fichas atuais.
    nova=get("https://apisidra.ibge.gov.br/values/t/9509/n6/3302700/p/all/v/367")
    if any(x.get("D1C")!="3302700" or x.get("D3C")!="367" for x in nova):
        raise ValueError("Escopo da sondagem CEMPRE inválido")
    years=sorted({int(x["D2C"]) for x in nova})
    if not set(range(2022,2025))<=set(years):
        raise ValueError("Sondagem CEMPRE incompleta")
    future=[y for y in years if y>2024]
    print("CEMPRE_NOVOS_ANOS",future,flush=True)
    candidate={}
    changed=[]
    for code,rows in data.items():
        old=json.loads((ASSETS/(code+".json")).read_text(encoding="utf-8"))
        if old["id"]!=code or old["codigo_ibge"]!="3302700":
            raise ValueError("Identificação da base divergente")
        csv_data=to_csv(rows,SPECS[code][3])
        if rows!=old["serie"] or csv_data!=(ASSETS/(code+".csv")).read_bytes().decode("utf-8"):
            changed.append(code)
            old["serie"]=rows
            if os.environ.get("GITHUB_RUN_ID"):
                old["fonte"]["auditoria_execucao"]="https://github.com/maricawiki/dados/actions/runs/"+os.environ["GITHUB_RUN_ID"]
        candidate[code+".json"]=json.dumps(old,ensure_ascii=False,indent=2)+"\n"
        candidate[code+".csv"]=csv_data
    if args.propor is not None:
        output=args.propor.resolve()
        if output==ROOT or ROOT in output.parents:
            raise ValueError("Proposta deve ficar fora da árvore versionada")
        output.mkdir(parents=True,exist_ok=False)
        for name,content in candidate.items():
            (output/name).write_text(content,encoding="utf-8")
        print("CEMPRE_PROPOSTA",len(candidate),"arquivos; nunca publicar sem revisão",flush=True)
    if changed or future:
        raise SystemExit("CEMPRE_REVISAR: alterações ou novos exercícios exigem revisão metodológica e editorial")
    print("CEMPRE_OK: 18 observações; 16 taxas; nenhuma variação em 2022",flush=True)

if __name__=="__main__":
    main()

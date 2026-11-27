#!/usr/bin/env python3
"""Proposta coordenada dos 17 indicadores fiscais já publicados (2019–2025).

Não atualiza a árvore de produção. Reutiliza a mesma resposta oficial de cada
anexo/exercício em todas as conciliações. Novos exercícios exigem ampliação
coordenada da série populacional e dos validadores editoriais.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
import produzir_dca as dca
import financas_royalties_divida as rd
import financas_percapita as pc
from observatorio_financas_siconfi_sondar import get_dca

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
RUN=os.environ.get("GITHUB_RUN_ID")
DATE=datetime.now(timezone.utc).date().isoformat()
REVENUE="Receitas Brutas Realizadas"
EXPENSE="Despesas Liquidadas"
YEARS=dca.YEARS
COLS={
 "FIN-001":("receita_bruta_realizada_reais","codigo_conta","estagio","fonte"),
 "FIN-002":("despesas_liquidadas_reais","despesas_empenhadas_reais","despesas_pagas_reais","codigo_conta","fonte"),
 "FIN-003":("despesas_liquidadas_reais","receita_bruta_realizada_reais","percentual_despesa_sobre_receita_bruta","fonte"),
 "FIN-004":("despesa_pessoal_liquidada_reais","fonte"),
 "FIN-005":("pessoal_liquidado_reais","receita_bruta_realizada_reais","relacao_pessoal_sobre_receita_bruta_pct","fonte"),
 "FIN-006":("investimentos_liquidados_reais","fonte"),
 "FIN-007":("investimentos_liquidados_reais","receita_bruta_realizada_reais","relacao_investimentos_sobre_receita_bruta_pct","fonte"),
}
def ratio(a,b):
    return (100*a/b).quantize(Decimal("0.000001"),rounding=ROUND_HALF_UP)

def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def encode(x):
    return (json.dumps(x,ensure_ascii=False,indent=2)+"\n").encode("utf-8")

def extract_base(fetch):
    data={code:[] for code in COLS}
    for y in YEARS:
        ic=fetch(y,"DCA-Anexo I-C")
        idata=fetch(y,"DCA-Anexo I-D")
        def read(code,col):return dca.select(idata,code,col,"Padrão")
        gross=dca.select(ic,"TotalReceitas",REVENUE,"Padrão")
        liquid=read("TotalDespesas",EXPENSE)
        committed=read("TotalDespesas","Despesas Empenhadas")
        paid=read("TotalDespesas","Despesas Pagas")
        people=read("DO3.1.00.00.00.00",EXPENSE)
        invest=read("DO4.4.00.00.00.00",EXPENSE)
        if not (gross>0 and 0<paid<=liquid<=committed and 0<people+invest<=liquid):
            raise ValueError(f"Estágios ou rubricas incompatíveis em {y}")
        values=[
            {"receita_bruta_realizada_reais":float(gross)},
            {"despesas_liquidadas_reais":float(liquid),"despesas_empenhadas_reais":float(committed),"despesas_pagas_reais":float(paid)},
            {"despesas_liquidadas_reais":float(liquid),"receita_bruta_realizada_reais":float(gross),"percentual_despesa_sobre_receita_bruta":float(ratio(liquid,gross))},
            {"despesa_liquidada_reais":float(people)},
            {"valor_percentual":float(ratio(people,gross)),"despesa_liquidada_reais":float(people),"receita_bruta_realizada_reais":float(gross)},
            {"despesa_liquidada_reais":float(invest)},
            {"valor_percentual":float(ratio(invest,gross)),"despesa_liquidada_reais":float(invest),"receita_bruta_realizada_reais":float(gross)},
        ]
        for code,record in zip(COLS,values):data[code].append({"ano":y,**record})
    return data

def csv_base(code,rows):
    out=io.StringIO(newline="")
    w=csv.writer(out,lineterminator="\n")
    w.writerow(("ano",*COLS[code]))
    def money(x):return f"{Decimal(str(x)):.2f}"
    def pct(x):return f"{Decimal(str(x)):.6f}"
    for x in rows:
        g=x.get("receita_bruta_realizada_reais")
        e=x.get("despesas_liquidadas_reais")
        p=x.get("despesa_liquidada_reais")
        if code=="FIN-001":values=(money(g),"TotalReceitas",REVENUE,"SICONFI_DCA_Anexo_I-C")
        elif code=="FIN-002":values=(money(e),money(x["despesas_empenhadas_reais"]),money(x["despesas_pagas_reais"]),"TotalDespesas","SICONFI_DCA_Anexo_I-D")
        elif code=="FIN-003":values=(money(e),money(g),pct(x["percentual_despesa_sobre_receita_bruta"]),"SICONFI_DCA_Anexos_I-C_I-D")
        elif code in ("FIN-004","FIN-006"):values=(money(p),"SICONFI_DCA_I-D")
        else:values=(money(p),money(g),pct(x["valor_percentual"]),"SICONFI_DCA_I-D_I-C")
        w.writerow((x["ano"],*values))
    return out.getvalue()

def produce(work,fetch):
    dca.ASSETS=rd.ASSETS=pc.ASSETS=work
    dca.get_dca=rd.get_dca=fetch
    result={}
    def stage(code,rows,csv_text):
        name=code+".json"
        old=json.loads((DATA/name).read_text(encoding="utf-8"))
        if old["id"]!=code or old["codigo_ibge"]!="3302700":raise ValueError("Identidade inválida "+code)
        raw=csv_text.encode("utf-8")
        # Evitar churn apenas por serialização ou nova data de execução.
        old_csv=(DATA/(code+".csv")).read_bytes()
        if rows==old["serie"] and raw.replace(b"\r\n",b"\n")==old_csv.replace(b"\r\n",b"\n"):return
        old["serie"]=rows
        if "fonte" in old:
            old["fonte"]["ultima_consulta_oficial"]=DATE
            if RUN:old["fonte"]["consulta_execucao"]="https://github.com/maricawiki/dados/actions/runs/"+RUN
        elif RUN:
            old["fontes"]["execucao_integracao"]="https://github.com/maricawiki/dados/actions/runs/"+RUN
        for filename,body in ((name,encode(old)),(code+".csv",raw)):
            (work/filename).write_bytes(body)
            result[filename]=body
    for code,rows in extract_base(fetch).items():stage(code,rows,csv_base(code,rows))
    for code,rows in dca.extract().items():stage(code,rows,dca.csv_file(rows,dca.SPECS[code][3]))
    for code,rows in rd.extract().items():stage(code,rows,rd.csv_data(rows,rd.SPECS[code][3]))
    for code,rows in pc.extract().items():stage(code,rows,pc.csv_file(rows))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix="dca_integral_") as tmp:
        root=Path(tmp)
        work=root/"observatorio"
        shutil.copytree(DATA,work)
        # O cache é exclusivamente em memória durante uma execução.
        fetch=lru_cache(maxsize=32)(get_dca)
        result=produce(work,fetch)
        if result:
            name="lote-02.manifest.json"
            manifest=json.loads((work/name).read_text(encoding="utf-8"))
            for filename,body in result.items():
                if filename not in manifest["files"]:raise ValueError("Fora do lote")
                manifest["files"][filename]=blob(body)
            result[name]=encode(manifest)
            (work/name).write_bytes(result[name])
        (root/"scripts").mkdir()
        for name in ("validar_lote_02.py","validar_financas_conciliacao.py"):
            target=root/"scripts"/name
            shutil.copy2(ROOT/"scripts"/name,target)
            subprocess.run([sys.executable,str(target)],check=True)
        if result and args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora da árvore")
            out.mkdir(parents=True,exist_ok=False)
            for name,raw in result.items():(out/name).write_bytes(raw)
        print("DCA_INTEGRAL",len(result),"arquivos alterados; consultas únicas",fetch.cache_info().misses,"; sem publicar",flush=True)

if __name__=="__main__":
    main()

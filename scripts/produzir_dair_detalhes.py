#!/usr/bin/env python3
"""PREV-005: carteira mensal do RPPS, exclusivamente MPS/CADPREV.

Gera e confere exclusivamente propostas minimizadas, sem escrita na árvore versionada.
NÃO deduplicar registros por CNPJ/nome: fundos podem ter múltiplas posições.
DAIR_CARTEIRA não informa divisão por plano financeiro/previdenciário.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,time,urllib.parse,urllib.request
from collections import defaultdict,Counter
from datetime import date
from decimal import Decimal,InvalidOperation
from io import StringIO
from pathlib import Path
from dair_minimizacao import sanitize_positions, validate_position

ROOT=Path(__file__).resolve().parents[1]
BASE="https://apicadprev.trabalho.gov.br"
HOST="apicadprev.trabalho.gov.br"
OUTPUT=ROOT/"observatorio"
CASH="Disponibilidades Financeiras"
LIMIT=5000
_last=0.
FIELDS={"no_ente","sg_uf","dt_ano","dt_mes_bimestre","no_segmento",
        "no_tipo_ativo","id_ativo","no_fundo","vl_total_atual"}

def fetch(endpoint, **filters):
    global _last
    wait=max(0.,1.25-(time.monotonic()-_last))
    if wait:time.sleep(wait)
    _last=time.monotonic()
    params={"no_ente":"Maricá","sg_uf":"RJ",**filters,"limit":LIMIT}
    url=BASE+"/"+endpoint+"?"+urllib.parse.urlencode(params)
    request=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0 MaricaWiki/Observatorio-PREV005","Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=60) as res:
        final=urllib.parse.urlparse(res.geturl())
        if final.hostname!=HOST or final.scheme!="https":raise ValueError("URL oficial redirecionada")
        body=res.read(30_000_001)
    if len(body)>30_000_000:raise ValueError("Resposta muito grande")
    payload=json.loads(body.decode("utf-8-sig"))
    if payload.get("success") is not True or not isinstance(payload.get("data"),list):
        raise ValueError("Resposta CADPREV inválida: "+endpoint)
    records=payload["data"]
    if len(records)>=LIMIT:raise ValueError("Limite de paginação atingido, exigir outro método")
    if any(r.get("no_ente")!="Maricá" or r.get("sg_uf")!="RJ" for r in records):
        raise ValueError("Filtro territorial incorreto")
    return records

def cents(raw):
    if raw is None or str(raw).strip()=="":
        raise ValueError("Valor da carteira não informado")
    txt=str(raw).replace("R$","").strip().replace(" ","")
    if "," in txt and "." in txt:
        txt=txt.replace(".","").replace(",",".") if txt.rfind(",")>txt.rfind(".") else txt.replace(",","")
    elif "," in txt:txt=txt.replace(",",".")
    try:d=Decimal(txt)
    except InvalidOperation as err:raise ValueError("Valor monetário inválido") from err
    if not d.is_finite() or d<0 or d*100!=(d*100).to_integral_value():
        raise ValueError("Valor monetário inválido ou com subcentavos: "+txt)
    return int(d*100)

def url_year(year):
    return BASE+"/DAIR_CARTEIRA?"+urllib.parse.urlencode({
        "no_ente":"Maricá","sg_uf":"RJ","dt_ano":year,"limit":LIMIT})

def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf-8")

def periods(first,last):
    year,month=first
    while (year,month)<=last:
        yield f"{year}-{month:02d}"
        year,month=(year+1,1) if month==12 else (year,month+1)

def produce(asof):
    ident=defaultdict(list)
    for row in fetch("DAIR_IDENTIFICACAO"):
        key=f'{int(row["dt_ano"])}-{int(row["dt_mes"]):02d}'
        ident[key].append(row)
    by_period=defaultdict(list)
    for year in range(2017,date.today().year+1):
        group=fetch("DAIR_CARTEIRA",dt_ano=year)
        if not group and year!=date.today().year:
            raise ValueError("Sem dados para "+str(year))
        if group and FIELDS-set(group[0]):
            raise ValueError("Schema da carteira alterado")
        for row in group:
            month=int(row["dt_mes_bimestre"])
            if not 1<=month<=12:raise ValueError("Mês DAIR inválido")
            key=f'{year}-{month:02d}'
            by_period[key].append(row)
    if not by_period or min(by_period)!="2017-01":
        raise ValueError("Histórico não começa em janeiro de 2017")
    ym=max((int(k[:4]),int(k[5:])) for k in by_period)
    if ym<(2026,7):raise ValueError("Série retornou competências insuficientes")
    years=defaultdict(list);summary=[];pending=[]
    expected=list(periods((2017,1),ym))
    if sorted(by_period)!=expected:raise ValueError("Lacunas entre competências oficiais")
    for key in expected:
        raw=by_period[key]
        missing=[r for r in raw if r.get("vl_total_atual") is None or str(r.get("vl_total_atual")).strip()==""]
        if missing:
            pending.append({"competencia":key,"posicoes_sem_valor":len(missing),"linhas_dair":len(raw)})
            print("DAIR_PENDENTE",key,len(missing),flush=True)
            continue
        ids=ident.get(key,[])
        closed=[r for r in ids if r.get("te_finalidade")=="ENCERRAMENTO_MES"]
        if not closed:raise ValueError("DAIR sem encerramento: "+key)
        selected=max(closed,key=lambda r:str(r.get("dt_envio") or ""))
        signatures=Counter(json.dumps(r,sort_keys=True,ensure_ascii=False) for r in raw)
        if any(n>1 for n in signatures.values()):
            raise ValueError("Linhas integralmente duplicadas em "+key)
        grouped=defaultdict(lambda:{"valor_centavos":0,"linhas":0})
        segments=defaultdict(int)
        for r in raw:
            amount=cents(r["vl_total_atual"])
            seg=str(r["no_segmento"] or "").strip()
            typ=str(r["no_tipo_ativo"] or "").strip() or "Não informado pelo MPS"
            asset=str(r["id_ativo"] or "").strip()
            name=" ".join(str(r["no_fundo"] or "").split())
            if not seg:raise ValueError("Segmento ausente: "+key)
            dest=grouped[(seg,typ,asset,name)]
            dest["valor_centavos"]+=amount;dest["linhas"]+=1
            segments[seg]+=amount
        positions=[
            {"segmento":s,"tipo_ativo":t,"id_ativo":i,
             "nome_ativo":n or "Ativo sem nome declarado",
             "valor_centavos":v["valor_centavos"],"linhas":v["linhas"]}
            for (s,t,i,n),v in grouped.items() if v["valor_centavos"]>0
        ]
        positions.sort(key=lambda p:(-p["valor_centavos"],p["segmento"],p["id_ativo"]))
        total=sum(segments.values());cash=segments.get(CASH,0)
        if total<=0 or sum(p["valor_centavos"] for p in positions)!=total:
            raise ValueError("Valores por fundos e segmentos não conciliam: "+key)
        year,month=map(int,key.split("-"))
        info={"competencia":key,"ano":year,"mes":month,
              "total_centavos":total,
              "investimentos_centavos":total-cash,
              "disponibilidades_centavos":cash,
              "segmentos_centavos":dict(sorted(segments.items())),
              "linhas_oficiais":len(raw),
              "ativos_com_saldo":len(positions),
              "identificacao":{
                "ultimo_envio":str(selected.get("dt_envio")),
                "data_posicao":str(selected.get("dt_posicao")),
                "versoes_identificacao":len(ids),
                "finalidade":"ENCERRAMENTO_MES"
              }}
        summary.append(info)
        safe=sanitize_positions(positions)
        for p in safe:validate_position(p)
        years[year].append({"competencia":key,"posicoes":safe})
    files={}
    for year,months in years.items():
        files[f"observatorio/PREV-005-carteira-{year}.json"]=encode({
            "id":"PREV-005","ano":year,"fonte":"MPS / DAIR_CARTEIRA",
            "url_fonte":url_year(year),"competencias":months})
    csvfile=StringIO()
    writer=csv.writer(csvfile,lineterminator="\n")
    writer.writerow(["competencia","ano","mes","total_reais","investimentos_reais",
                     "disponibilidades_reais","linhas_dair","ativos_com_saldo","data_envio","fonte"])
    for r in summary:
        writer.writerow([
            r["competencia"],r["ano"],r["mes"],
            str(Decimal(r["total_centavos"])/100),
            str(Decimal(r["investimentos_centavos"])/100),
            str(Decimal(r["disponibilidades_centavos"])/100),
            r["linhas_oficiais"],r["ativos_com_saldo"],
            r["identificacao"]["ultimo_envio"],url_year(r["ano"])
        ])
    files["observatorio/PREV-005.csv"]=csvfile.getvalue().encode("utf-8")
    files["observatorio/PREV-005.json"]=encode({
        "id":"PREV-005","titulo":"Carteira de investimentos do RPPS",
        "municipio":"Maricá","codigo_ibge":"3302700","uf":"RJ",
        "dimensao":"institucional","funcao_tematica":"09",
        "fonte":"Ministério da Previdência Social — API CADPREV",
        "tabelas":["DAIR_CARTEIRA","DAIR_IDENTIFICACAO"],
        "moeda":"BRL","unidade":"centavos inteiros nos JSONs; reais nominais nos CSVs",
        "primeira_competencia":summary[0]["competencia"],
        "ultima_competencia":summary[-1]["competencia"],
        "quantidade_competencias":len(summary),"competencias_da_fonte":len(expected),
        "competencias_pendentes":pending,"conferencia_em":asof,
        "observacoes":[
            "vl_total_atual de todas as posições é somado por competência; linhas para o mesmo fundo não são descartadas",
            "Investimentos excluem Disponibilidades Financeiras; o total informado inclui ambos",
            "A tabela DAIR_CARTEIRA não informa plano financeiro/previdenciário ou fundo segregado",
            "Identificacao traz versões e data de envio, mas a carteira não vincula cada linha à versão",
            "Saldos nominais não representam rentabilidade ou receita",
            "Competências com posição sem vl_total_atual permanecem fora da série quantitativa; não atribuir valor zero nem interpolar"
        ],"serie":summary
    })
    return files,summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--propor",type=Path)
    a=p.parse_args()
    try:
        old=json.loads((OUTPUT/"PREV-005.json").read_text(encoding="utf-8"))
        files,summary=produce(old["conferencia_em"])
        if any(not name.startswith("observatorio/PREV-005") for name in files):
            raise ValueError("Escopo inesperado")
        different=[name for name,data in files.items() if not (ROOT/name).is_file() or (ROOT/name).read_bytes()!=data]
        if a.propor:
            out=a.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Diretório dentro do repositório")
            out.mkdir(parents=True,exist_ok=False)
            for name,data in files.items():(out/Path(name).name).write_bytes(data)
    except Exception as exc:
        raise SystemExit("DAIR_FALHA: "+type(exc).__name__) from None
    print("DAIR_MINIMIZADO",len(summary),"competências;",len(files),"arquivos; divergências",different,flush=True)
    if different:raise SystemExit("DAIR_REVISAR: fonte alterada ou nova competência")
    print("DAIR_MINIMIZADO_OK",flush=True)

if __name__=="__main__":
    main()

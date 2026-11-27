#!/usr/bin/env python3
"""Auditoria dos quantitativos DRAA/Maricá na API oficial: sem publicação.

Confere categorias, planos, situação e retificações. Nunca mistura
'Servidores Iminentes' com 'Servidores' nem multiplica rubricas por órgão.
"""
from __future__ import annotations

import collections
import json
import time
import urllib.parse
import urllib.request
from decimal import Decimal

BASE="https://apicadprev.trabalho.gov.br/"
KNOWN = {2019:(2449,643,110),2023:(4251,728,162),2024:(4360,754,167),2025:(4438,792,175)}
CATS=("Servidores","Aposentados","Pensionistas")
LIMIT=5000
last=0.

def query(table,**filters):
    global last
    delay=max(0.,1.25-(time.monotonic()-last))
    if delay:time.sleep(delay)
    last=time.monotonic()
    params=urllib.parse.urlencode({"no_ente":"Maricá","sg_uf":"RJ",**filters,"limit":LIMIT})
    req=urllib.request.Request(BASE+table+"?"+params,headers={
        "Accept":"application/json","User-Agent":"Mozilla/5.0 MaricaWiki/Observatorio-DRAA"
    })
    with urllib.request.urlopen(req,timeout=45) as resp:
        data=resp.read(15_000_001)
        if len(data)>15_000_000:raise ValueError("Resposta excessiva")
        if urllib.parse.urlparse(resp.geturl()).hostname!="apicadprev.trabalho.gov.br":raise ValueError("Host inesperado")
        doc=json.loads(data.decode("utf-8-sig"))
    if doc.get("success") is not True or not isinstance(doc.get("data"),list):raise ValueError("Formato não reconhecido")
    rows=doc["data"]
    if len(rows)>=LIMIT:raise ValueError("Dados incompletos: exige paginação")
    if any(r.get("no_ente")!="Maricá" or r.get("sg_uf")!="RJ" for r in rows):
        raise ValueError("Filtro territorial não aplicado")
    return rows

def n(v):
    if v is None or str(v).strip()=="": return 0
    val=Decimal(str(v))
    if not val.is_finite() or val!=int(val) or val<0:raise ValueError("Contagem inválida")
    return int(val)

def main():
    enc=query("DRAA_ENCAMINHAMENTO")
    rows=query("DRAA_ESTATISTICA")
    print("DRAA_AUDITORIA",json.dumps({
        "total_encaminhamentos":len(enc),"total_estatisticas":len(rows),
        "anos":sorted({int(x["dt_exercicio"]) for x in rows}),
    },ensure_ascii=False),flush=True)
    by_year=collections.defaultdict(list)
    for r in rows:by_year[int(r["dt_exercicio"])].append(r)
    latest_enc={}
    for r in enc:
        ano=int(r["dt_exercicio"])
        if r.get("te_situacao")=="Documentos Digitalizados":
            latest_enc.setdefault(ano,[]).append(str(r.get("dt_envio")))
    for ano, group in sorted(by_year.items()):
        envios=sorted({str(r.get("dt_envio")) for r in group})
        situa=sorted({str(r.get("te_situacao")) for r in group})
        statuses=latest_enc.get(ano,[])
        bycat=collections.defaultdict(int)
        byplan=collections.defaultdict(lambda: collections.defaultdict(int))
        bykey=collections.Counter()
        distinct_org=set()
        for r in group:
            cat=r.get("tp_populacao")
            plan=r.get("tp_plano")
            qt=n(r.get("qt_grupo_masc"))+n(r.get("qt_grupo_fem"))
            bycat[cat]+=qt
            byplan[plan][cat]+=qt
            bykey[(str(r.get("dt_envio")),str(r.get("tp_plano")),str(r.get("tp_populacao")),str(r.get("cnpj_orgao")),str(r.get("no_cat_populacao")),str(r.get("no_regra_enquadramento")),str(r.get("no_criterio_aposentadoria")))]+=1
            distinct_org.add(str(r.get("cnpj_orgao")))
        # No AEPS, os ativos incluem Servidores e Servidores Iminentes.
        totals=(bycat["Servidores"]+bycat["Servidores Iminentes"],bycat["Aposentados"],bycat["Pensionistas"])
        matched=KNOWN.get(ano)
        summary={
            "ano":ano,"linhas":len(group),"envios":envios,"situacoes":situa,
            "encaminhamentos_aprovados":statuses,
            "tipos_populacao":dict(bycat),
            "quantidade_por_plano":{k:dict(v) for k,v in byplan.items()},
            "orgaos":len(distinct_org),
            "chaves_exatamente_duplicadas":sum(v-1 for v in bykey.values() if v>1),
            "total_de_segurados_e_beneficiarios":sum(totals),
            "comparacao_aeps":("IGUAL" if totals==matched else "DIFERENTE") if matched else "SEM_BASE_AEPS",
            "aeps":matched,
        }
        print("DRAA_SERIE_MARICA",json.dumps(summary,ensure_ascii=False,default=str),flush=True)

if __name__=="__main__":
    main()

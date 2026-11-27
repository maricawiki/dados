#!/usr/bin/env python3
"""Monitora novos DRAA/retificações da API CADPREV, sem atualizar arquivos.

Falha de forma explícita se um ano publicado mudou ou surgiu referência nova:
a atualização deverá passar por nova conciliação editorial antes da publicação.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from observatorio_previdencia_cadprev_api_auditar import query, n

ROOT = Path(__file__).resolve().parents[1]
IDS = ("PREV-001","PREV-002","PREV-003","PREV-004")
def main():
    records = query("DRAA_ESTATISTICA")
    encaminhamentos = query("DRAA_ENCAMINHAMENTO")
    aprovados={}
    for row in encaminhamentos:
        if row["te_situacao"]=="Documentos Digitalizados":
            ano=int(row["dt_exercicio"])
            if ano in aprovados:
                raise ValueError(f"Mais de um DRAA aprovado no exercício {ano}; revisar manualmente")
            aprovados[ano]=str(row["dt_envio"])
    grouped=defaultdict(list)
    for row in records:
        ano=int(row["dt_exercicio"])
        if ano>=2015:
            grouped[ano].append(row)
    with (ROOT/"observatorio/PREV-001.csv").open(encoding="utf-8", newline="") as f:
        baseline=list(csv.DictReader(f))
    published={int(row["draa"].removeprefix("DRAA")):row for row in baseline}
    if len(published)!=len(baseline):
        raise ValueError("DRAA repetido no arquivo publicado")
    if not published:
        raise ValueError("Série pública vazia")
    issues=[]
    for ano in sorted(grouped):
        group=grouped[ano]
        envios={str(r["dt_envio"]) for r in group}
        situacoes={str(r["te_situacao"]) for r in group}
        if len(envios)!=1 or situacoes!={"Documentos Digitalizados"} or aprovados.get(ano) not in envios:
            issues.append(f"{ano}: demonstrativo substituído, retificado ou status divergente")
            continue
        counts=defaultdict(int)
        for r in group:
            if r["tp_plano"] not in ("Financeiro","Previdenciário"):
                issues.append(f"{ano}: plano não esperado {r['tp_plano']}")
                continue
            if r["tp_massa"]!="Civil":
                issues.append(f"{ano}: massa diferente de Civil")
                continue
            cat=r["tp_populacao"]
            if cat not in ("Servidores","Servidores Iminentes","Aposentados","Pensionistas"):
                issues.append(f"{ano}: categoria nova {cat}")
                continue
            counts[cat]+=n(r.get("qt_grupo_masc"))+n(r.get("qt_grupo_fem"))
        ativos=counts["Servidores"]+counts["Servidores Iminentes"]
        apos=counts["Aposentados"]
        pens=counts["Pensionistas"]
        total=ativos+apos+pens
        actual=(ativos,apos,pens,total)
        if ano not in published:
            issues.append(f"NOVO_DRAA:{ano} totais={actual}")
            continue
        old=published[ano]
        expected=tuple(int(old[k]) for k in ("ativos","aposentados","pensionistas","total"))
        if actual!=expected:
            issues.append(f"RETIFICACAO:{ano} publicado={expected} API={actual}")
        print(f"OK DRAA{ano}: {actual}, envio={next(iter(envios))}",flush=True)
    for ano in sorted(published):
        if ano not in grouped:
            issues.append(f"DRAA_AUSENTE:{ano} não retornado pela API")
    # Detecta alterações nos planos mesmo quando o consolidado não muda.
    meta_geral=json.loads((ROOT/"observatorio/PREV-001.json").read_text(encoding="utf-8"))
    for fonte in meta_geral["proveniencia_api"]:
        ano=int(fonte["referencia"].removeprefix("DRAA"))
        group=grouped.get(ano,[])
        if not group:
            continue
        if {str(row["dt_envio"]) for row in group}!={fonte["dt_envio"]}:
            issues.append(f"ENVIO_DRAA_ALTERADO:{ano}")
            continue
        counts=defaultdict(lambda: defaultdict(int))
        for row in group:
            plan=row["tp_plano"]
            cat=row["tp_populacao"]
            counts[plan][cat]+=n(row.get("qt_grupo_masc"))+n(row.get("qt_grupo_fem"))
        for nome,esperado in fonte["planos"].items():
            atual={
                "servidores":counts[nome]["Servidores"],
                "iminentes":counts[nome]["Servidores Iminentes"],
                "aposentados":counts[nome]["Aposentados"],
                "pensionistas":counts[nome]["Pensionistas"],
            }
            atual["ativos"]=atual["servidores"]+atual["iminentes"]
            if any(esperado[key]!=value for key,value in atual.items()):
                issues.append(f"PLANO_DRAA_RETIFICADO:{ano}:{nome}")

    for ident in IDS:
        meta=json.loads((ROOT/f"observatorio/{ident}.json").read_text(encoding="utf-8"))
        if meta["anos_referencias"]!=sorted(published):
            issues.append(f"{ident}: referências inconsistentes entre JSON e CSV")
    if issues:
        for issue in issues:
            print("CADPREV_REVISAR",issue,flush=True)
        raise SystemExit(f"{len(issues)} mudança(s) no CADPREV exigem revisão e atualização auditada")
    print(f"OK: {len(published)} referências do MPS sem divergência nem novo DRAA.",flush=True)

if __name__=="__main__":
    main()

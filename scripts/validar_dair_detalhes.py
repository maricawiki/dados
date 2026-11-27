#!/usr/bin/env python3
"""Valida detalhes públicos DAIR contra os agregados, sem rede."""
import json
from collections import defaultdict
from pathlib import Path
from dair_minimizacao import validate_position, CASH

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"

def main():
    summary=json.loads((DATA/"PREV-005.json").read_text(encoding="utf-8"))
    by={r["competencia"]:r for r in summary["serie"]}
    seen=set()
    for path in sorted(DATA.glob("PREV-005-carteira-*.json")):
        annual=json.loads(path.read_text(encoding="utf-8"))
        if annual["id"]!="PREV-005" or not annual["url_fonte"].startswith("https://apicadprev.trabalho.gov.br/DAIR_CARTEIRA?"):
            raise ValueError("Origem DAIR inválida")
        for month in annual["competencias"]:
            key=month["competencia"]
            if key in seen or key not in by or not key.startswith(str(annual["ano"])+"-"):
                raise ValueError("Competência inválida")
            seen.add(key)
            positions=month["posicoes"]
            ref=by[key]
            if len(positions)!=ref["ativos_com_saldo"]:raise ValueError("Contagem divergente")
            segments=defaultdict(int)
            for row in positions:
                validate_position(row)
                segments[row["segmento"]]+=row["valor_centavos"]
            if dict(segments)!={k:v for k,v in ref["segmentos_centavos"].items() if v>0}:
                raise ValueError("Segmentos não conciliam")
            if sum(segments.values())!=ref["total_centavos"] or segments.get(CASH,0)!=ref["disponibilidades_centavos"]:
                raise ValueError("Total divergente")
    if seen!=set(by):raise ValueError("Cobertura incompleta")
    print("DAIR_OK",len(seen),"competências; detalhes minimizados e conciliados")

if __name__=="__main__":
    main()

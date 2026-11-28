#!/usr/bin/env python3
"""Extrai estabelecimentos do mesmo espelho RAIS/ONMT auditado, com cobertura parcial."""
import csv,io,json
from decimal import Decimal,ROUND_HALF_UP
YEARS=list(range(2014,2026))
PORTES=("Micro","Pequena","Média","Grande")
SPECS={
"ECO-006":("Estabelecimentos no painel RAIS por porte","estabelecimentos-rais-porte","4.2.2","total"),
"ECO-007":("Variação anual dos estabelecimentos no painel RAIS","variacao-anual-estabelecimentos-rais","4.2.5","variacao"),
}
ANCHORS={2014:1583,2019:1625,2023:2427,2024:2615,2025:2736}
def integer(x):
 d=Decimal(str(x))
 if not d.is_finite() or d<0 or d!=d.to_integral_value():raise ValueError(f"Contagem inválida: {x}")
 return int(d)
def extract_estabelecimentos(file):
 import duckdb
 with duckdb.connect() as con:
  records=con.execute("""
   SELECT period,"tipo_abertura.1","abertura.1",
          "tipo_abertura.2","abertura.2",valor
   FROM read_parquet(?) WHERE codigo_ibge='330270'
     AND variaveis='abs_rais_estabelecimentos'
     AND period BETWEEN 2014 AND 2025 AND valor IS NOT NULL
  """,[str(file)]).fetchall()
 if len(records)!=60:raise ValueError("Não há 60 registros esperados")
 by_year={}
 for y,t1,a1,t2,a2,value in records:
  if t2 is not None or a2 is not None:raise ValueError("Recorte imprevisto")
  key="Total" if (t1,a1)==("Total","Total") else a1 if t1=="Porte das empresas" else None
  if key not in ("Total",)+PORTES:raise ValueError("Porte desconhecido")
  row=by_year.setdefault(int(y),{})
  if key in row:raise ValueError("Porte duplicado")
  row[key]=integer(value)
 if sorted(by_year)!=YEARS:raise ValueError("Série incompleta")
 total=[];growth=[];previous=None
 for y in YEARS:
  row=by_year[y]
  if set(row)!=set(PORTES)|{"Total"}:raise ValueError("Portes ausentes")
  if sum(row[p] for p in PORTES)!=row["Total"]:raise ValueError("Portes não somam total")
  if y in ANCHORS and row["Total"]!=ANCHORS[y]:raise ValueError("Âncora auditada divergente")
  total.append({"ano":y,"valor":row["Total"],
    "portes":[{"porte":p,"quantidade":row[p]} for p in PORTES]})
  rate=(Decimal(row["Total"]-previous)/Decimal(previous)*100).quantize(
   Decimal("0.000001"),rounding=ROUND_HALF_UP) if previous is not None else None
  growth.append({"ano":y,"valor":str(rate) if rate is not None else None,
    "estabelecimentos_atual":row["Total"],"estabelecimentos_anterior":previous,
    "status":"calculado_com_ressalva" if previous is not None else "sem_base_anterior"})
  previous=row["Total"]
  print("ESTABELECIMENTOS_RAIS",json.dumps({"ano":y,"total":row["Total"],
     "portes":{p:row[p] for p in PORTES},"taxa":str(rate) if rate is not None else None},
     ensure_ascii=False),flush=True)
 assert sum(v["valor"] is not None for v in growth)==11
 return {"ECO-006":total,"ECO-007":growth}
def csv_text(series,kind):
 out=io.StringIO(newline="");w=csv.writer(out,delimiter=";",lineterminator="\n")
 if kind=="total":
  w.writerow(["ano","total","micro","pequena","media","grande"])
  for r in series:
   values={s["porte"]:s["quantidade"] for s in r["portes"]}
   w.writerow([r["ano"],r["valor"]]+[values[p] for p in PORTES])
 else:
  w.writerow(["ano","variacao_percentual","atual","anterior","status"])
  for r in series:
   w.writerow([r["ano"],r["valor"] if r["valor"] is not None else "",
    r["estabelecimentos_atual"],r["estabelecimentos_anterior"] or "",r["status"]])
 return out.getvalue()

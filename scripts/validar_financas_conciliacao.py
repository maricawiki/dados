#!/usr/bin/env python3
"""Concilia indicadores fiscais publicados sem acesso externo."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/"observatorio"
def dec(x):return Decimal(str(x))
def load(code):return {x["ano"]:x for x in json.loads((DATA/f"FIN-{code:03}.json").read_text(encoding="utf-8"))["serie"]}
s={i:load(i) for i in range(1,18)}
def eq(a,b):assert dec(a)==dec(b),(a,b)
def ratio(a,b):return (100*dec(a)/dec(b)).quantize(Decimal("0.000001"),rounding=ROUND_HALF_UP)
for y in s[1]:
    r={i:s[i][y] for i in s}
    gross=dec(r[1]["receita_bruta_realizada_reais"])
    liquid=dec(r[2]["despesas_liquidadas_reais"])
    assert 0<dec(r[2]["despesas_pagas_reais"])<=liquid<=dec(r[2]["despesas_empenhadas_reais"])
    eq(r[3]["receita_bruta_realizada_reais"],gross)
    eq(r[3]["despesas_liquidadas_reais"],liquid)
    eq(r[3]["percentual_despesa_sobre_receita_bruta"],ratio(liquid,gross))
    for base,derived in ((4,5),(6,7)):
        amount=dec(r[base]["despesa_liquidada_reais"])
        eq(r[derived]["despesa_liquidada_reais"],amount)
        eq(r[derived]["receita_bruta_realizada_reais"],gross)
        eq(r[derived]["valor_percentual"],ratio(amount,gross))
    eq(dec(r[9]["uniao"])+dec(r[9]["estado"]),r[9]["valor"])
    eq(r[10]["transferencias"],r[9]["valor"])
    eq(r[10]["receita_bruta"],gross)
    eq(r[10]["valor"],ratio(r[9]["valor"],gross))
    eq(dec(r[11]["valor"])+dec(r[11]["intra"]),liquid)
    eq(sum(dec(f["valor"]) for f in r[11]["funcoes"]),r[11]["valor"])
    eq(dec(r[12]["royalties_uniao"])+dec(r[12]["participacao_especial"])+dec(r[12]["royalties_estado"] or 0),r[12]["valor"])
    eq(r[13]["receitas_identificadas"],r[12]["valor"])
    eq(r[13]["receita_bruta"],gross)
    eq(r[13]["valor"],ratio(r[12]["valor"],gross))
    eq(dec(r[14]["juros_encargos"])+dec(r[14]["amortizacao"]),r[14]["valor"])
    for code,numerator in ((15,gross),(16,r[8]["valor"]),(17,r[6]["despesa_liquidada_reais"])):
        row=r[code]
        eq(row["numerador_reais"],numerator)
        if y==2023:assert row["valor"] is None and row["populacao_habitantes"] is None
        else:eq(row["valor"],(dec(numerator)/dec(row["populacao_habitantes"])).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
print("FIN-001 a FIN-017: totais, estágios, funções, participações e per capita conciliados")

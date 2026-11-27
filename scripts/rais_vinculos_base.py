#!/usr/bin/env python3
"""Extrai cinco indicadores agregados RAIS/MTE 2014–2025 de Maricá.

A fonte primária dos índices é o Painel da Rede de Observatórios do Trabalho
do MTE. O espelho independente NÃO é publicação oficial e é usado apenas com
SHA256 fixo, identificação do painel e conciliação 2023–2025 à Tabela 4
OFICIAL da RAIS 2025. Nenhum microdado ou Parquet é versionado.

Não interpretar vínculo empregatício como indivíduo único.
"""
import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html import escape
import io
import json
import re
import tempfile
import unicodedata
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"observatorio"
SOURCE="https://github.com/jtrecenti/painel-onmt/releases/download/dados-2026-09-02/rais.parquet"
SOURCE_SHA="cc1d85dd8afaf5d5f650d55bfd299dd33764c08157734aa6e928748d345404d9"
SOURCE_MTE="https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/rais/rais-2025/rais-2025"
SOURCE_MTE_FILE="https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/acoes-e-programas/programas-projetos-acoes-obras-e-atividades/estatisticas-trabalho/rais/rais-2025/rais-2025-tabelas.xlsx/@@download/file"
OFFICIAL_STOCK={2023:33532,2024:35384,2025:37493}
YEARS=list(range(2014,2026))
CBO_GRANDES_GRUPOS={
 "0":"0 — Forças Armadas, policiais e bombeiros militares",
 "1":"1 — Dirigentes do poder público, organizações e empresas",
 "2":"2 — Profissionais das ciências e das artes",
 "3":"3 — Técnicos de nível médio",
 "4":"4 — Trabalhadores de serviços administrativos",
 "5":"5 — Trabalhadores dos serviços e vendedores do comércio",
 "6":"6 — Trabalhadores agropecuários, florestais e da pesca",
 "7":"7 — Produção industrial: trabalhadores de processos artesanais",
 "8":"8 — Produção industrial: operadores de máquinas e sistemas",
 "9":"9 — Trabalhadores de manutenção e reparação",
}
CBO_OFICIAL="https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/cbo/informacoes-gerais"
CATEGORIES={
 "TRB-009":("Empregos formais por sexo","empregos-formais-sexo","5.3.1","sexo"),
 "TRB-010":("Variação anual do estoque de empregos formais femininos","variacao-empregos-formais-femininos","5.3.2","variacao"),
 "TRB-011":("Empregos formais por escolaridade","empregos-formais-escolaridade","5.2.8","escolaridade"),
 "TRB-012":("Empregos formais por escolaridade e sexo","empregos-formais-escolaridade-sexo","5.3.5","escolaridade_sexo"),
 "TRB-013":("Empregos formais por grande grupo ocupacional","empregos-formais-grupo-ocupacional","5.2.6","grupo_ocupacional"),
}

def normalize(x):
    return "".join(c for c in unicodedata.normalize("NFD",str(x).casefold())
                   if unicodedata.category(c)!="Mn")

def retrieve(cache=None):
    if cache:
        data=Path(cache)
        if not data.is_file():raise ValueError("Parquet de auditoria ausente")
        with data.open("rb") as fh:
            h=sha256()
            while part:=fh.read(4_194_304):h.update(part)
        if h.hexdigest()!=SOURCE_SHA:raise ValueError("SHA256 diferente do espelho auditado")
        return data,False
    temp=Path(tempfile.mkdtemp(prefix="maricawiki_rais_"))
    path=temp/"rais.parquet"
    req=urllib.request.Request(SOURCE,headers={"User-Agent":"MaricaWiki/1.0","Accept":"application/octet-stream,*/*"})
    digest=sha256()
    size=0
    try:
        with urllib.request.urlopen(req,timeout=180) as res, path.open("wb") as dst:
            while part:=res.read(4_194_304):
                size+=len(part)
                if size>340_000_000:raise ValueError("Fonte RAIS maior que limite aprovado")
                digest.update(part);dst.write(part)
        if not 200_000_000<size<340_000_000 or digest.hexdigest()!=SOURCE_SHA:
            raise ValueError("Arquivo RAIS ONMT sofreu alteração ou chegou incompleto")
        print("FONTE",SOURCE,"BYTES",size,"SHA256",digest.hexdigest(),flush=True)
        return path,True
    except Exception:
        path.unlink(missing_ok=True)
        temp.rmdir()
        raise

def integer(val):
    if val is None or not isinstance(val,(float,int)) or val<0 or val!=round(val):
        raise ValueError(f"RAIS contém contagem não inteira, ausente ou negativa: {val!r}")
    return int(val)

def extract(path):
    import duckdb
    con=duckdb.connect()
    recs=con.execute("""
      SELECT period,"tipo_abertura.1","abertura.1","tipo_abertura.2","abertura.2",
             "tipo_abertura.3","abertura.3",valor
      FROM read_parquet(?)
      WHERE codigo_ibge='330270' AND variaveis='abs_rais_emp_formal'
        AND period BETWEEN 2014 AND 2025
        AND valor IS NOT NULL
    """,[str(path)]).fetchall()
    print("RAIS_ABERTURA_TERCEIRO_NIVEL",recs[:5],flush=True)
    rows=[{"year":int(y),"t1":t1,"a1":a1,"t2":t2,"a2":a2,"valor":integer(v)}
          for y,t1,a1,t2,a2,t3,a3,v in recs]
    totals={}
    for r in rows:
        if r["t1"]=="Total" and r["t2"]=="Total":
            y=r["year"]
            if y in totals:raise ValueError(f"RAIS total duplicado: {y}")
            totals[y]=r["valor"]
    if sorted(totals)!=YEARS:
        raise ValueError(f"Estoque municipal sem todos os anos: {sorted(totals)}")
    if {y:totals[y] for y in OFFICIAL_STOCK}!=OFFICIAL_STOCK:
        raise ValueError(f"ONMT divergente da tabela oficial RAIS 2025: {[totals[y] for y in OFFICIAL_STOCK]}")
    print("RAIS_ESTOQUES",[{"ano":y,"vinculos":totals[y]} for y in YEARS],flush=True)
    if totals[2016]!=15054:
        print("AVISO: RAIS 2016 revisada difere do retrato DIEESE 2016 (15054):",totals[2016],flush=True)
    def one_year(year,t1,t2):
        result={}
        for r in rows:
            if r["year"]!=year or r["t1"]!=t1:continue
            second=r["t2"]
            if t2 is None:
                if second not in (None,""):continue
                cat=r["a1"]
            else:
                if second!=t2 or r["a1"] not in ("Total", None, ""):continue
                cat=r["a2"]
            if cat in (None,"","Total"):continue
            if cat in result:raise ValueError(f"Duplicidade {year} {t1}/{t2} {cat}")
            result[str(cat)]=r["valor"]
        if len(result)<2 or sum(result.values())!=totals[year]:
            raise ValueError(f"Categorias não exaustivas em {year}: {t1}/{t2} = {result}, total={totals[year]}")
        return result
    sexes={y:one_year(y,"Sexo",None) for y in YEARS}
    for y,items in sexes.items():
        if set(items)!={"Feminino","Masculino"}:
            raise ValueError(f"Sexo sem categorias uniformes em {y}: {items}")
    educ={y:one_year(y,"Escolaridade",None) for y in YEARS}
    occupation={}
    for y in YEARS:
        raw=one_year(y,"Total","Grupo ocupacional")
        if set(raw)-set(CBO_GRANDES_GRUPOS):
            raise ValueError(f"Grandes grupos ocupacionais desconhecidos: {set(raw)-set(CBO_GRANDES_GRUPOS)}")
        occupation[y]={CBO_GRANDES_GRUPOS[k]:v for k,v in raw.items()}
    crosses={}
    for y in YEARS:
        vals={}
        for r in rows:
            if r["year"]!=y or (r["t1"],r["t2"])!=("Sexo","Escolaridade"):
                continue
            if r["a1"]=="Total" or r["a2"]=="Total" or not r["a1"] or not r["a2"]:continue
            cat=str(r["a1"])+" · "+str(r["a2"])
            if cat in vals:raise ValueError(f"Duplicidade sexo x escolaridade {y}: {cat}")
            vals[cat]=r["valor"]
        if not vals or sum(vals.values())!=totals[y]:
            raise ValueError(f"Sexo/escolaridade não concilia com estoque em {y}")
        for sexo in ("Feminino","Masculino"):
            subtotal=sum(v for key,v in vals.items() if key.startswith(sexo+" · "))
            if subtotal!=sexes[y][sexo]:
                raise ValueError(f"Escolaridade cruzada não concilia com {sexo} em {y}")
        for cat,value in educ[y].items():
            subtotal=sum(v for key,v in vals.items() if key.endswith(" · "+cat))
            if subtotal!=value:raise ValueError(f"Escolaridade cruzada não concilia {cat} em {y}")
        crosses[y]=vals
    def as_series(groups):
        return [{"ano":y,"total":totals[y],
                 "categorias":[{"categoria":k,"vinculos":groups[y][k]} for k in sorted(groups[y],key=normalize)]}
                for y in YEARS]
    result={
      "TRB-009":as_series(sexes),
      "TRB-011":as_series(educ),
      "TRB-012":as_series(crosses),
      "TRB-013":as_series(occupation),
    }
    changes=[]
    for previous,current in zip(YEARS,YEARS[1:]):
        start=sexes[previous]["Feminino"]
        end=sexes[current]["Feminino"]
        if start<=0:raise ValueError(f"Sem estoque feminino anterior em {previous}")
        pct=((Decimal(end)/Decimal(start))-1)*100
        changes.append({"ano":current,"ano_anterior":previous,
                        "vinculos_femininos_ano_anterior":start,
                        "vinculos_femininos":end,
                        "variacao_absoluta":end-start,
                        "variacao_percentual":format(pct.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP),"f")})
    result["TRB-010"]=changes
    for code,serie in result.items():
        print("INDICADOR",code,"LINHAS",len(serie),"INICIO",serie[0],"FIM",serie[-1],flush=True)
    return result,totals

def csv_string(series,kind):
    buf=io.StringIO(newline="")
    writer=csv.writer(buf,delimiter=";",lineterminator="\n")
    if kind=="variacao":
        writer.writerow(["ano","ano_anterior","vinculos_femininos_ano_anterior","vinculos_femininos",
                         "variacao_absoluta","variacao_percentual"])
        for r in series:writer.writerow([r[k] for k in
            ("ano","ano_anterior","vinculos_femininos_ano_anterior","vinculos_femininos","variacao_absoluta","variacao_percentual")])
    else:
        writer.writerow(["ano","categoria","vinculos","total_municipal"])
        for r in series:
            for cat in r["categorias"]:
                writer.writerow([r["ano"],cat["categoria"],cat["vinculos"],r["total"]])
    return buf.getvalue()


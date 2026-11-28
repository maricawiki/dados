#!/usr/bin/env python3
"""Monitorar telefonia fixa e banda larga fixa, sem publicar.
Comparar dezembro com dezembro; não confundir acessos com pessoas.
Mudanças do ZIP sem diferenças municipais são informativas.
"""
import csv
import hashlib
import io
import json
import zipfile
import unicodedata
import re
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

DATA=Path(__file__).resolve().parents[1]/"observatorio"
URL="https://www.anatel.gov.br/dadosabertos/paineis_de_dados/meu_municipio/meu_municipio.zip"
NAME="Meu_Municipio_Acessos.csv"
SERVICES={"TEL-001":"Telefonia Fixa","TEL-002":"Banda Larga Fixa"}

def fetch():
    with urlopen(Request(URL,headers={"User-Agent":"MaricaWiki/1.0"}),timeout=85) as response:
        loc=urlsplit(response.geturl())
        if loc.scheme!="https" or loc.hostname not in {"www.anatel.gov.br","anatel.gov.br"}:
            raise ValueError("Origem ANATEL divergente")
        raw=response.read(50_000_001)
    if len(raw)>50_000_000:raise ValueError("ZIP excede limite")
    return raw

def parse(raw):
    result={service:{} for service in SERVICES.values()}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=[x for x in z.infolist() if x.filename==NAME]
        if len(entries)!=1 or entries[0].file_size>500_000_000:
            raise ValueError("Arquivo interno inesperado")
        with z.open(entries[0]) as fd, io.TextIOWrapper(fd,encoding="utf-8-sig",errors="strict",newline="") as f:
            reader=csv.DictReader(f,delimiter=";")
            required={"Ano","Mês","Acessos","Serviço","Código IBGE","Município","UF"}
            if not required.issubset(reader.fieldnames or []):raise ValueError("Schema ANATEL mudou")
            for row in reader:
                if row["Código IBGE"]!="3302700" or row["Serviço"] not in result:continue
                name="".join(c for c in unicodedata.normalize("NFD",row["Município"].strip().casefold()) if unicodedata.category(c)!="Mn")
                if row["UF"].strip().upper()!="RJ" or not re.fullmatch(r"marica(?:\s*(?:[-/]\s*rj|\(rj\)))?",name):
                    raise ValueError(f"Município divergente: {row['Município']!r}, UF {row['UF']!r}")
                y,m,n=int(row["Ano"]),int(row["Mês"]),int(row["Acessos"])
                if not 1900<=y<=2100 or not 1<=m<=12 or n<0:raise ValueError("Competência ou valor inválido")
                series=result[row["Serviço"]]
                if (y,m) in series:raise ValueError("Competência duplicada")
                series[y,m]=n
    if not all(result.values()):raise ValueError("Sem cobertura municipal")
    return result

def reference():
    result={}
    for code,service in SERVICES.items():
        meta=json.loads((DATA/(code+".json")).read_text(encoding="utf-8"))
        if meta["id"]!=code or meta["codigo_ibge"]!="3302700" or meta["tipo_servico_oficial"]!=service or meta["url_arquivo_oficial"]!=URL:
            raise ValueError("Identidade local inválida")
        with (DATA/(code+".csv")).open(encoding="utf-8",newline="") as f:
            rows=list(csv.DictReader(f))
        if [(int(r["ano"]),int(r["mes"]),int(r["acessos"])) for r in rows]!=[(r["ano"],r["mes"],r["acessos"]) for r in meta["serie"]]:
            raise ValueError("CSV e JSON divergem")
        if any(r["codigo_ibge"]!="3302700" or r["servico"]!=service for r in rows):raise ValueError("Identidade CSV")
        annual={(r["ano"],r["mes"]):r["acessos"] for r in meta["serie"]}
        if len(annual)!=len(rows) or any(m!=12 for _,m in annual):raise ValueError("Base anual inválida")
        result[service]=annual
    return result

def compare(official,baseline):
    report={}
    for service,old in baseline.items():
        current=official[service]
        report[service]={
            "ausentes":[f"{y}-{m:02d}" for y,m in sorted(old.keys()-current.keys())],
            "revisoes":[{"ano":y,"publicado":old[y,m],"oficial":current[y,m]} for y,m in sorted(old.keys()&current.keys()) if old[y,m]!=current[y,m]],
            "novos_dezembros":[{"ano":y,"acessos":n} for (y,m),n in sorted(current.items()) if m==12 and (y,m) not in old],
            "ultima_competencia":f"{max(current)[0]}-{max(current)[1]:02d}",
        }
    return report

def main():
    baseline=reference()
    raw=fetch()
    report=compare(parse(raw),baseline)
    print("ANATEL_MONITOR",json.dumps({"sha256_zip":hashlib.sha256(raw).hexdigest(),"servicos":report},ensure_ascii=False),flush=True)
    if any(x["ausentes"] for x in report.values()):
        raise SystemExit("Cobertura histórica ausente: revisar fonte; sem publicação")
    if any(x["revisoes"] or x["novos_dezembros"] for x in report.values()):
        print("::warning::ANATEL: alteração editorial a revisar; nenhum dado publicado",flush=True)
    else:print("ANATEL_OK: série anual publicada conferida",flush=True)

if __name__=="__main__":main()

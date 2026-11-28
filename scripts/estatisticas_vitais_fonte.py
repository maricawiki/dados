#!/usr/bin/env python3
"""Agrega estatísticas vitais oficiais de Maricá, sem armazenar microdados.

Fonte: Secretaria Estadual de Saúde RJ, arquivos anuais em CSV/ZIP.
Unidade: mãe residente em Maricá (SINASC) e óbito infantil de residente (SIM).
Módulo interno do produtor público. Retorna somente agregados e controles de cobertura. Não mostrar nomes, endereços, CEP, datas ou identificadores.
"""
from __future__ import annotations
import csv, io, json, sys, unicodedata, urllib.request, zipfile
from collections import Counter
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE="https://sistemas.saude.rj.gov.br/tabnetbd"
MONTH=None
MUNICIPIO={"330270","3302700"}
HEADERS={"User-Agent":"MaricaWiki-Observatorio/1.0 (estatisticas vitais agregadas)"}
def norm(s):
    return " ".join("".join(
        c for c in unicodedata.normalize("NFKD",str(s or "").strip().casefold())
        if not unicodedata.combining(c)
    ).split())
def file_url(kind,year):
    return (f"{BASE}/sinasc/dadoscsv/dnrj{year}.zip" if kind=="SINASC"
            else f"{BASE}/sim/DadosCSV/doerj{year}.zip")
def get(kind,year):
    url=file_url(kind,year)
    request=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(request,timeout=65) as response:
        dest=urlsplit(response.geturl())
        if dest.scheme!="https" or dest.hostname!="sistemas.saude.rj.gov.br":raise ValueError("Fonte SES-RJ divergente")
        data=response.read(60_000_001)
    if len(data)>60_000_000:
        raise ValueError(f"Arquivo muito grande, não processar {kind} {year}")
    return data,url

def read_and_count(kind,year):
    payload,url=get(kind,year)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries=[p for p in archive.namelist() if p.lower().endswith(".csv")]
        if len(entries)!=1:
            raise ValueError(f"{kind} {year}: esperado um CSV por ZIP, foram {entries}")
        if archive.getinfo(entries[0]).file_size>1_500_000_000:raise ValueError("CSV acima do limite")
        with archive.open(entries[0]) as binary:
            txt=io.TextIOWrapper(binary,encoding="latin-1",newline="",errors="strict")
            reader=csv.reader(txt,delimiter=";")
            headers=[h.strip() for h in next(reader)]
            positions={norm(name):i for i,name in enumerate(headers)}
            if len(positions)!=len(headers):
                raise ValueError(f"Colunas repetidas {kind} {year}")
            name="Parturiente - Município de residência - código" if kind=="SINASC" else "Município de residência - código"
            k=positions.get(norm(name))
            if k is None:
                raise ValueError(f"Campo municipal de residência não encontrado: {kind} {year}")
            flag=positions.get(norm("Óbito infantil")) if kind=="SIM" else None
            fetal=positions.get(norm("Óbito fetal")) if kind=="SIM" else None
            anos=positions.get(norm("Idade em anos")) if kind=="SIM" else None
            if kind=="SIM" and (flag is None or fetal is None or anos is None):
                raise ValueError(f"SIM {year}: falta campo de validação de óbito infantil/fetal/idade")
            total=0;residents=0; infant_flags=Counter(); fetal_flags=Counter(); ages=Counter()
            for row in reader:
                total+=1
                if k>=len(row) or row[k].strip() not in MUNICIPIO:continue
                residents+=1
                if kind=="SIM":
                    infant_flags[norm(row[flag])] += 1
                    fetal_flags[norm(row[fetal])] += 1
                    if norm(row[flag])=="sim":
                        if norm(row[fetal]) not in {"nao","não"} or norm(row[anos])!="000":
                            raise ValueError("Inconsistência do registro infantil: revisar fonte, sem expor registros")
                        ages[norm(row[anos])] += 1
            if not total or not residents:raise ValueError("Arquivo sem cobertura municipal")
            out={"ano":year,"tipo":kind,"url":url,
                 "registros_arquivo":total,"residentes_marica":residents}
            if kind=="SIM":
                out["obito_infantil_categorias"]=dict(infant_flags)
                out["obito_fetal_categorias"]=dict(fetal_flags)
                out["idade_anos_obitos_com_flag_infantil"]=dict(ages)
            return out


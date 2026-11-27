#!/usr/bin/env python3
"""Extrai leitos CNES de dezembro, 2007–2025, de arquivos originais MS.

Estatística agregada municipal. Não registra nomes, endereços, dados pessoais.
O arquivo fonte conserva campos diferentes segundo o ano; todos são
normalizados por NOMES DE CAMPOS. Leitos de UTI NÃO são somados aos leitos
de internação, porque são variáveis distintas do arquivo de origem.
"""
from __future__ import annotations
import concurrent.futures, csv, io, json, re, unicodedata
import urllib.request, urllib.error, zipfile
from collections import defaultdict

BASE="https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/"
YEARS=range(2007,2026)
HEADERS={"User-Agent":"MaricaWiki-Observatorio/1.0; fonte-publica"}
def normalize(s):
    s="".join(t for t in unicodedata.normalize("NFKD",str(s or "")) if not unicodedata.combining(t))
    return re.sub(r"_+","_",re.sub(r"[^A-Z0-9]","_",s.upper())).strip("_")
def to_num(v):
    if v in ("",None,"-","—"):return 0
    return int(str(v).strip())
def extract(year):
    fn=f"Leitos_csv_{year}.zip" if year>=2025 else f"Leitos_{year}.csv"
    req=urllib.request.Request(BASE+fn,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=85) as resp: payload=resp.read(85_000_000)
    if len(payload)>=85_000_000:raise ValueError(f"Arquivo {year} excedeu limite de segurança")
    if fn.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files=[n for n in archive.namelist() if n.lower().endswith(".csv")]
            if len(files)!=1:raise ValueError(f"ZIP {year}: arquivos CSV inesperados {files}")
            with archive.open(files[0]) as f:
                data=f.read()
    else:data=payload
    text=io.StringIO(data.decode("utf-8-sig",errors="replace"))
    first=text.readline()
    sep=";" if first.count(";")>first.count(",") else ","
    head=[normalize(h) for h in next(csv.reader([first],delimiter=sep))]
    idx={name:i for i,name in enumerate(head)}
    def ix(*options):
        for op in options:
            if op in idx:return idx[op]
        raise ValueError(f"Campo ausente em {year}: {options}; disponíveis {head}")
    i_comp=ix("COMP")
    i_ibge=idx.get("CO_IBGE")
    i_city=ix("MUNICIPIO")
    i_uf=ix("UF")
    i_cnes=ix("CNES")
    i_existing=ix("LEITOS_EXISTENTES","LEITOS_EXISTENTE")
    i_sus=ix("LEITOS_SUS")
    i_uti_existing=ix("UTI_TOTAL_EXIST","UTI_TOTAL_EXISTENTE","UTI_TOTAL_EXISTENTES")
    i_uti_sus=ix("UTI_TOTAL_SUS")
    i_typ=ix("DS_TIPO_UNIDADE")
    values=defaultdict(int)
    by_type=defaultdict(lambda:{"hospitais":set(),"leitos_existentes":0,"leitos_sus":0,"uti_existentes":0,"uti_sus":0})
    establishments=set()
    n=0
    for row in csv.reader(text,delimiter=sep):
        if len(row)<len(head):continue
        if row[i_comp].strip()!=str(year)+"12":continue
        if row[i_uf].strip().upper()!="RJ":continue
        municipal=((i_ibge is not None and row[i_ibge].strip() in ("330270","3302700"))
                   or normalize(row[i_city]).startswith("MARICA"))
        if not municipal:continue
        n+=1
        cnes=row[i_cnes].strip()
        if not cnes:raise ValueError(f"CNES vazio em {year}")
        if cnes in establishments:
            raise ValueError(f"Estabelecimento repetido em dezembro {year}: exigir auditoria")
        establishments.add(cnes)
        nums={"leitos_existentes":to_num(row[i_existing]),"leitos_sus":to_num(row[i_sus]),
              "uti_existentes":to_num(row[i_uti_existing]),"uti_sus":to_num(row[i_uti_sus])}
        if nums["leitos_sus"]>nums["leitos_existentes"] or nums["uti_sus"]>nums["uti_existentes"]:
            raise ValueError(f"Quantidades SUS inconsistentes em {year}")
        for key,val in nums.items():values[key]+=val
        typ=row[i_typ].strip() or "Não informado"
        by_type[typ]["hospitais"].add(cnes)
        for key,val in nums.items():by_type[typ][key]+=val
    if n==0:raise ValueError(f"Sem registros de Maricá em dezembro de {year}; não publicar zero")
    return {"ano":year,"competencia":year*100+12,"fonte":BASE+fn,
            "hospitais_com_leitos":len(establishments),
            "leitos_existentes":values["leitos_existentes"],"leitos_sus":values["leitos_sus"],
            "uti_existentes":values["uti_existentes"],"uti_sus":values["uti_sus"],
            "detalhe_tipo":{name:{"hospitais":len(info["hospitais"]), **{key:val for key,val in info.items() if key!="hospitais"}}
                            for name,info in sorted(by_type.items())}}
def main():
    output=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(extract,y):y for y in YEARS}
        for f in concurrent.futures.as_completed(tasks):
            y=tasks[f]
            try:
                result=f.result()
            except Exception as exc:
                print("LEITOS_FALHA",y,type(exc).__name__,str(exc)[:240],flush=True)
                continue
            print("LEITOS_SERIE",json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
            output.append(result)
    print("LEITOS_SAIDA",len(output),"anos entre",len(YEARS),flush=True)
    if len(output)<12:raise SystemExit("Série insuficiente para publicação. Investigar faltas.")
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Extrai exclusivamente taxas agregadas municipais oficiais INEP.
TLS verificado por padrão; recuperação excepcional de ZIP histórico somente
quando seu SHA-256 já foi fixado e conferido. Nunca aceitar hash novo por TLS inseguro.
"""
import argparse,hashlib,io,json,ssl,urllib.request,urllib.error,zipfile,time
from openpyxl import load_workbook
from urllib.parse import urlsplit

BASE="https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/{y}/TDI_{y}_MUNICIPIOS.zip"
KEYS=[f"FUN_{i:02d}_CAT_0" for i in range(1,10)]+[f"MED_{i:02d}_CAT_0" for i in range(1,4)]
NETWORKS=("Total","Municipal","Estadual","Federal","Privada")
EXPECTED_SHA={}
def number(v):
    if v is None or str(v).strip() in ("","--","-","nan"):return None
    x=float(str(v).replace(",","."))
    if not 0<=x<=100:raise ValueError("Taxa fora de 0..100")
    return round(x,3)
def retrieve(year,expected_sha):
    url=BASE.format(y=year); error=None
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/zip,*/*"})
            try:
                response=urllib.request.urlopen(request,timeout=65)
            except urllib.error.URLError as exc:
                if not expected_sha or not isinstance(exc.reason,ssl.SSLCertVerificationError):raise
                response=urllib.request.urlopen(request,context=ssl._create_unverified_context(),timeout=65)
            with response:
                dest=urlsplit(response.geturl())
                if dest.scheme!="https" or dest.hostname!="download.inep.gov.br":raise ValueError("Origem INEP divergente")
                data=response.read(33_000_001)
            if len(data)>33_000_000:raise ValueError("ZIP acima do limite")
            if not zipfile.is_zipfile(io.BytesIO(data)):raise ValueError("Arquivo recebido não é ZIP")
            sha=hashlib.sha256(data).hexdigest()
            if expected_sha and expected_sha!=sha:raise ValueError("SHA-256 do ZIP oficial divergiu: exigir auditoria da revisão")
            return url,data,sha
        except Exception as exc:
            error=exc
            if attempt<2:time.sleep(2*(attempt+1))
    raise RuntimeError(f"download falhou ano {year}: {error}")
def year_data(year,expected_sha):
    url,data,sha=retrieve(year,expected_sha)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names=[name for name in z.namelist() if name.lower().endswith(".xlsx")]
        if len(names)!=1:raise ValueError(f"Esperado um único XLSX, localizados {names}")
        item=z.getinfo(names[0])
        if item.file_size>20000000:raise ValueError("Planilha acima do limite")
        workbook=load_workbook(io.BytesIO(z.read(names[0])),read_only=True,data_only=True)
        sheet=workbook["MUNICIPIO"]
        lines=sheet.iter_rows(values_only=True)
        cols=None;result={}
        for row_no,row in enumerate(lines,start=1):
            if row_no==9:
                cols={str(v).strip():i for i,v in enumerate(row) if v is not None}
                if "NO_CATEGORIA" in cols:
                    location_field="NO_CATEGORIA"
                    network_field="NO_DEPENDENCIA"
                    field_map={code:code for code in KEYS}
                elif "TIPOLOCA" in cols:
                    location_field="TIPOLOCA"
                    network_field="DEPENDAD"
                    field_map={**{f"FUN_{i:02d}_CAT_0":f"TDI_F{i-1:02d}" for i in range(1,10)},
                               **{f"MED_{i:02d}_CAT_0":f"TDI_M{i:02d}" for i in range(1,4)}}
                else:raise ValueError("Cabeçalho de rede e localização desconhecido")
                required={"CO_MUNICIPIO","NO_MUNICIPIO",location_field,network_field}|set(field_map.values())
                if not required.issubset(cols):
                    raise ValueError("Cabeçalhos oficiais inesperados: "+str(sorted(required-set(cols))))
            if row_no<10:continue
            municipality=str(row[cols["CO_MUNICIPIO"]]).strip()
            if municipality not in ("3302700","3302700.0"):continue
            if str(row[cols[location_field]]).strip()!="Total":continue
            network=str(row[cols[network_field]]).strip()
            if network not in NETWORKS:continue
            if network in result:raise ValueError(f"Duplicidade Maricá/{year}/{network}")
            if str(row[cols["NO_MUNICIPIO"]]).strip()!="Maricá":
                raise ValueError("Código do município sem nome Maricá")
            result[network]={code:number(row[cols[field_map[code]]]) for code in KEYS}
        if set(result)!=set(NETWORKS):
            raise ValueError("Dependências ausentes: "+str(sorted(set(NETWORKS)-set(result))))
        if all(v is None for v in result["Total"].values()):
            raise ValueError("Nenhuma taxa municipal publicada")
        workbook.close()
        return {"ano":year,"municipio":"3302700","fonte":url,"arquivo":names[0],"sha256_zip":sha,"redes":result}

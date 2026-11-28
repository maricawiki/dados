#!/usr/bin/env python3
"""Consultas municipais agregadas à Receita Federal. Sem arquivos de sessão ou dados individuais."""
import base64
import csv
import html
import io
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import http.cookiejar
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path

HOST="https://www8.receita.fazenda.gov.br"
BASE=HOST+"/SimplesNacional/Aplicacoes/ATBHE/estatisticasSinac.app/"
PATH=BASE+"EstatisticasOptantesPorDataMunicipio.aspx"
MUNICIPIOS=BASE+"ConsultaMunicipios.aspx"
UA={"User-Agent":"Mozilla/5.0 (MaricaWiki-AuditoriaSIMEI/1.0)",
    "Accept":"text/html,application/xhtml+xml,*/*"}
FIELDS={
 "option":"ctl00$ctl00$Conteudo$AntesTabela$droplistOpcao",
 "date":"ctl00$ctl00$Conteudo$AntesTabela$txtDtIni",
 "uf":"ctl00$ctl00$Conteudo$AposTabela$ddlUf",
 "hfUF":"ctl00$ctl00$Conteudo$AposTabela$hfUF",
 "hfMunicipios":"ctl00$ctl00$Conteudo$AposTabela$hfMunicipios",
 "hfCheck":"ctl00$ctl00$Conteudo$AposTabela$hfCheck",
 "submit":"ctl00$ctl00$Conteudo$AntesTabela$btnExibir",
}

def simei_url(year):
 encoded=base64.b64encode(str(year).encode()).decode()
 return PATH+"?"+urllib.parse.urlencode({
  "tipoConsulta":"2","optanteSimei":"","anoConsulta":encoded
 })

def form_inputs(body):
 # Decodifica campos ASP.NET sem materializar cookie ou salvar credenciais.
 tags=re.findall(r"<input\b[^>]*>",body,re.I)
 selected={}
 for tag in tags:
  name=re.search(r'\bname="([^"]+)"',tag)
  if not name:continue
  value=re.search(r'\bvalue="([^"]*)"',tag)
  selected[name.group(1)]=html.unescape(value.group(1)) if value else ""
 return {k:v for k,v in selected.items() if k.startswith("__")}

def open_text(opener,url,form=None):
 data=urllib.parse.urlencode(form).encode() if form is not None else None
 req=urllib.request.Request(url,data=data,
    headers={**UA,**({"Content-Type":"application/x-www-form-urlencoded"} if data else {})},
    method="POST" if data is not None else "GET")
 for attempt in range(3):
  try:
   with opener.open(req,timeout=45) as response:
    if response.status!=200:raise ValueError("HTTP "+str(response.status))
    if urllib.parse.urlsplit(response.geturl()).scheme!='https' or urllib.parse.urlsplit(response.geturl()).hostname!='www8.receita.fazenda.gov.br':raise ValueError('Origem Receita divergente')
    raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Resposta acima do limite')
    body=raw.decode('utf-8','strict')
    if not body:raise ValueError("Resposta vazia")
    return body
  except (OSError,TimeoutError) as exc:
   if attempt==2:raise
   time.sleep(attempt+1)
 raise AssertionError("Inalcançável")

def city_id(opener):
 req=urllib.request.Request(MUNICIPIOS,
   data=urllib.parse.urlencode({"uf":"RJ"}).encode(),
   headers={**UA,"Content-Type":"application/x-www-form-urlencoded",
      "X-Requested-With":"XMLHttpRequest"},method="POST")
 with opener.open(req,timeout=40) as response:
  if urllib.parse.urlsplit(response.geturl()).scheme!="https" or urllib.parse.urlsplit(response.geturl()).hostname!="www8.receita.fazenda.gov.br":raise ValueError("Origem Receita divergente")
  raw=response.read(250001)
  if len(raw)>250000:raise ValueError("Lista municipal acima do limite")
  data=raw.decode("utf-8","strict")
 options=[(key,html.unescape(name.strip())) for key,name in
    re.findall(r'<option[^>]*value="([^"]+)"[^>]*>([^<]*)</option>',data,re.I)]
 marica=[(key,name) for key,name in options if name.upper()=="MARICA"]
 if len(options)!=92 or len(marica)!=1 or marica[0][0]!="5853":
  raise ValueError(f"Lista municipal da Receita mudou: {len(options)} opções; MARICA={marica}")
 return marica[0][0]

def fetch_year(opener,year,code):
 url=simei_url(year)
 initial=open_text(opener,url)
 if f"ANO {year}" not in initial or "Optantes por UF e Município - Simei" not in initial:
  raise ValueError(f"Página incorreta no exercício {year}")
 token=form_inputs(initial)
 if not all(k in token for k in ("__VIEWSTATE","__EVENTVALIDATION","__VIEWSTATEGENERATOR")):
  raise ValueError("Campos de validação ASP.NET não encontrados")
 form={**token,"__EVENTTARGET":FIELDS["option"],"__EVENTARGUMENT":"",
       FIELDS["option"]:"Por Município",FIELDS["uf"]:"RJ"}
 mode=open_text(opener,url,form)
 if not re.search(r'<option selected="selected" value="Por Município">',mode):
  raise ValueError("Modo municipal não selecionado")
 final={**form_inputs(mode),"__EVENTTARGET":"","__EVENTARGUMENT":"",
        FIELDS["option"]:"Por Município",FIELDS["date"]:f"31/12/{year}",
        FIELDS["uf"]:"RJ",FIELDS["hfUF"]:"RJ",
        FIELDS["hfMunicipios"]:"'"+code+"'",FIELDS["hfCheck"]:"false",
        FIELDS["submit"]:"Exibir Dados"}
 body=open_text(opener,url,final)
 subtitle=f"Total de Empresas Optantes em 31/12/{year}, no estado RJ, por Município e Data"
 if subtitle not in html.unescape(re.sub("<[^>]*>"," ",body)):
  # Espaços e quebras HTML variam, mas não se aceita consulta de data ou UF erradas.
  clean=re.sub(r"\s+"," ",html.unescape(re.sub("<[^>]*>"," ",body)))
  if subtitle not in clean:
   print("MEI_DIAGNOSTICO_ANO",json.dumps({"ano":year,
      "texto_relevante":clean[clean.find("ANO "+str(year)):clean.find("ANO "+str(year))+1100],
      "tem_tabela":"gridDados" in body,
      "mensagem":re.findall(r'<span[^>]+lblMensagem[^>]*>(.*?)</span>',body,re.I|re.S)},
      ensure_ascii=False),flush=True)
   raise ValueError(f"Subtítulo/datas divergentes em {year}")
 table=re.search(r'<table[^>]+id="[^"]*gridDados"[^>]*>(.*?)</table>',body,re.I|re.S)
 if not table:raise ValueError(f"Faltou tabela oficial em {year}")
 rows=re.findall(r"<tr\b[^>]*>(.*?)</tr>",table.group(1),re.I|re.S)
 data=[]
 for row in rows:
  cells=re.findall(r"<td\b[^>]*>(.*?)</td>",row,re.I|re.S)
  if len(cells)!=2:continue
  data.append([re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>","",c))).strip()
               for c in cells])
 if len(data)!=2 or data[0][0]!="MARICA" or data[1][0]!="TOTAL":
  raise ValueError(f"Tabela municipal inesperada em {year}: {data[:3]}")
 numeric=data[0][1]
 if not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})*|[0-9]+",numeric):
  raise ValueError(f"Número não reconhecido em {year}: {numeric}")
 if data[1][1]!=numeric:raise ValueError("Total da grade não reconcilia com município")
 amount=int(numeric.replace(".",""))
 if amount<=0:raise ValueError("MEI não positivo: "+str(year))
 m=re.search(r'id="[^"]*lblDataEstatistica"[^>]*>(.*?)</span>',body,re.I|re.S)
 consolidated=html.unescape(re.sub("<[^>]*>","",m.group(1))).strip() if m else None
 if not consolidated or "Posição Consolidada" not in consolidated:
  raise ValueError("Data de consolidação oficial ausente")
 return {"ano":year,"valor":amount,"data_referencia":f"31/12/{year}",
         "posicao_consolidada":consolidated,"municipio_sinac":code,"fonte":url}

def sinac_url(year):
    enc=base64.b64encode(str(year).encode()).decode()
    return PATH+"?"+urllib.parse.urlencode({"tipoConsulta":"1","anoConsulta":enc})

def extract_year(opener,year,municipio):
    url=sinac_url(year)
    initial=open_text(opener,url)
    if f"ANO {year}" not in initial or "Optantes por UF e Município - Sinac" not in initial:
        raise ValueError(f"SINAC: tela incorreta no ano {year}")
    tokens=form_inputs(initial)
    expected={"__VIEWSTATE","__EVENTVALIDATION","__VIEWSTATEGENERATOR"}
    if not expected.issubset(tokens):raise ValueError("Sem tokens de estado da consulta")
    post={**tokens,"__EVENTTARGET":FIELDS["option"],"__EVENTARGUMENT":"",
          FIELDS["option"]:"Por Município",FIELDS["uf"]:"RJ"}
    middle=open_text(opener,url,post)
    if not re.search(r'<option selected="selected" value="Por Município">',middle):
        raise ValueError("Modo Por Município não aplicado")
    request={**form_inputs(middle),"__EVENTTARGET":"","__EVENTARGUMENT":"",
             FIELDS["option"]:"Por Município",FIELDS["date"]:f"31/12/{year}",
             FIELDS["uf"]:"RJ",FIELDS["hfUF"]:"RJ",
             FIELDS["hfMunicipios"]:"'"+municipio+"'",
             FIELDS["hfCheck"]:"false",FIELDS["submit"]:"Exibir Dados"}
    body=open_text(opener,url,request)
    stripped=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",body)))
    expected=f"Total de Empresas Optantes em 31/12/{year}, no estado RJ, por Município e Data"
    if expected not in stripped:
        raise ValueError(f"Resposta SINAC sem data/UF esperada {year}: "+
                         stripped[stripped.find(f"ANO {year}"):][:500])
    table=re.search(r'<table[^>]*id="[^"]*gridDados"[^>]*>(.*?)</table>',
                    body,re.I|re.S)
    if not table:raise ValueError(f"SINAC sem resultado tabular {year}")
    rows=re.findall(r"<tr\b[^>]*>(.*?)</tr>",table.group(1),re.I|re.S)
    data=[]
    for row in rows:
        cells=re.findall(r"<td\b[^>]*>(.*?)</td>",row,re.I|re.S)
        if len(cells)==2:
            data.append([re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>","",x))).strip()
                         for x in cells])
    if len(data)!=2 or data[0][0]!="MARICA" or data[1][0]!="TOTAL":
        raise ValueError(f"SINAC: município e linha total não conciliáveis {year}: {data[:3]}")
    numeric=data[0][1]
    if numeric!=data[1][1] or not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})*|[0-9]+",numeric):
        raise ValueError(f"Total SINAC inesperado em {year}")
    total=int(numeric.replace(".",""))
    if total<=0:raise ValueError(f"Total SINAC inválido em {year}")
    consolidated=re.search(r'id="[^"]*lblDataEstatistica"[^>]*>(.*?)</span>',body,re.I|re.S)
    revision=html.unescape(re.sub("<[^>]*>","",consolidated.group(1))).strip() if consolidated else None
    if not revision or "Posição Consolidada" not in revision:
        raise ValueError(f"Sem data de consolidação em {year}")
    return {"ano":year,"valor":total,"data_referencia":f"31/12/{year}",
            "posicao_consolidada":revision,"municipio_sinac":municipio,"fonte":url}


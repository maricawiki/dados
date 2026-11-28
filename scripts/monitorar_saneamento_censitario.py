#!/usr/bin/env python3
"""Conferência integral dos sete recortes censitários SAN-001–003 no SIDRA.
Não mistura domicílios censitários com indicadores anuais SINISA.
"""
import csv,json,re,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from urllib.error import URLError
DATA=Path(__file__).resolve().parents[1]/"observatorio"
SPECS = {
    "SAN-001": {
        "slug": "abastecimento-agua",
        "years": [(2010, 8112, 42810, "1398", "96", "61", "92853"),
                  (2022, 25870, 73454, "6803", "381", "1821", "72144")],
        "totals": {2010: "0", 2022: "72129"},
        "categories": {"72129": 73454, "72144": 25870, "72145": 10542, "72153": 37042},
    },
    "SAN-002": {
        "slug": "esgotamento-rede-geral",
        "years": [(2010, 5300, 42810, "1394", "96", "11558", "92855"),
                  (2022, 13014, 73454, "6805", "381", "11558", "72110")],
        "totals": {2010: "0", 2022: "46292"},
        "categories": {"46292": 73454, "72110": 13014, "72111": 12444,
                       "72112": 41712, "72113": 3277, "92858": 1085,
                       "72114": 783, "72115": 1117, "92861": 22},
    },
    "SAN-003": {
        "slug": "coleta-lixo",
        "years": [(2000, 16405, 22853, "1439", "96", "67", "2520"),
                  (2010, 39889, 42810, "1395", "96", "67", "2520"),
                  (2022, 72793, 73454, "6892", "381", "67", "2520")],
        "totals": {2000: "0", 2010: "0", 2022: "10972"},
        "categories": {"10972": 73454, "2520": 72793, "72120": 67445,
                       "72121": 5348, "72122": 290, "72123": 9,
                       "72124": 244, "1091": 118},
    },
}


def rows(name):
    with (DATA/name).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def baseline():
    result=[]
    for code,spec in SPECS.items():
        meta=json.loads((DATA/(code+".json")).read_text(encoding="utf-8"))
        if meta["id"]!=code or meta["codigo_ibge"]!="3302700" or meta["natureza"]!="observacao_censitaria":raise ValueError("Metodologia divergente")
        table=rows(code+".csv")
        if [int(r["ano"]) for r in table]!=meta["anos"] or len(table)!=len(spec["years"]):raise ValueError("Cobertura divergente")
        details=rows(code+"-categorias-2022.csv")
        cats={r["categoria_sidra_codigo"]:int(r["domicilios"]) for r in details}
        if len(cats)!=len(details) or cats!=spec["categories"] or any(r["ano"]!="2022" for r in details):raise ValueError("Categorias divergentes")
        for r,(y,n,d,t,v,c,k) in zip(table,spec["years"]):
            if int(r["ano"])!=y or int(r["domicilios_atendidos"])!=n or int(r["domicilios_referencia"])!=d or abs(float(r["percentual"])-100*n/d)>=0.000051 or r["fonte_id"]!=f"IBGE_SIDRA_{t}_v{v}_c{c}_{k}":raise ValueError("Série divergente")
            expected={k:n,spec["totals"][y]:d}
            if y==2022:expected.update(cats)
            result.append((code,y,t,v,c,expected))
    return result

def parse(data,year,var,clas):
    if not isinstance(data,list) or len(data)<2:raise ValueError("SIDRA sem cobertura")
    hdr=data[0]
    def field(label):
        matches=[k for k,v in hdr.items() if re.fullmatch(r"D\d+C",k) and isinstance(v,str) and label in v.casefold()]
        if len(matches)!=1:raise ValueError("Dimensão SIDRA não reconhecida: "+label)
        return matches[0]
    city,variable,yr=field("município"),field("variável"),field("ano")
    cat=[k for k in hdr if re.fullmatch(r"D\d+C",k) and k not in (city,variable,yr)]
    if len(cat)!=1:raise ValueError("Classificação inesperada")
    out={}
    for row in data[1:]:
        if row[city]!="3302700" or row[variable]!=var or row[yr]!=str(year) or row.get("NC")!="6" or "domicílio" not in row.get("MN","").casefold():raise ValueError("Município, ano, variável ou unidade divergentes")
        k=row[cat[0]]
        if k in out:raise ValueError("Categoria duplicada")
        value=row.get("V","")
        if value.isdigit():out[k]=int(value)
        elif value in ("...","-","X",".."):out[k]=None
        else:raise ValueError("Valor desconhecido")
    return out

def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={"User-Agent":"MaricaWiki/1.0","Accept":"application/json"}),timeout=45) as r:
                dst=urlsplit(r.geturl())
                if dst.scheme!="https" or dst.hostname!="apisidra.ibge.gov.br":raise ValueError("Origem divergente")
                raw=r.read(1_000_001)
                if len(raw)>1_000_000:raise ValueError("Resposta excessiva")
                return json.loads(raw)
        except URLError:
            if attempt==2:raise
            time.sleep(2*(attempt+1))
def main():
    items=baseline()
    for code,y,t,v,c,expected in items:
        url=f"https://apisidra.ibge.gov.br/values/t/{t}/n6/3302700/v/{v}/p/{y}/c{c}/all"
        actual=parse(fetch(url),y,v,c)
        diff={k:{"publicado":n,"oficial":actual.get(k)} for k,n in expected.items() if actual.get(k)!=n}
        if diff:
            print("SAN_REVISAR",code,y,json.dumps(diff),flush=True)
            raise SystemExit("Revisão censitária: não publicar automaticamente")
        print("SAN_CENSO_OK",code,y,len(expected),"categorias",flush=True)
        time.sleep(.25)
    print("SAN_CENSO_CONCLUIDO",len(items),"recortes; sem publicar")
if __name__=="__main__":main()

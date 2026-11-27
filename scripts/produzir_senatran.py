#!/usr/bin/env python3
"""Taxas anuais por frota: ISP-RJ (numeradores) + SENATRAN (dezembro de cada ano).

Taxas derivadas Maricá Wiki, NÃO taxas oficiais ISP. Não estima frota, não trata
2014--2025 como observações mensais, não interpreta frota registrada como circulante.
O denominador total inclui os tipos cadastrados no RENAVAM, não apenas automóveis.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
FROTA=DATA/"FROTA-MARICA-ANUAL.json"
BASE="https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-"
NAMESPACE="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
START="<!-- INICIO TAXA POR FROTA SENATRAN -->"
END="<!-- FIM TAXA POR FROTA SENATRAN -->"
POL_START="<!-- INICIO OBS POLICIAIS ISP -->"
POL_END="<!-- FIM OBS POLICIAIS ISP -->"
SPEC=[
 ("SEG-002","roubos-veiculos","roubo de veículos","9.2.3"),
 ("SEG-014","furtos-veiculos","furto de veículos","9.2.15"),
 ("SEG-023","recuperacao-veiculos","recuperação de veículos","9.3.9"),
]
POLICE={
 "SEG-032":("policiais-militares-mortos-servico","9.1.10"),
 "SEG-033":("policiais-civis-mortos-servico","9.1.11"),
}
POLICE_METHOD="https://www.ispdados.rj.gov.br/MetodologiaPoliciaisMortosEmServico.html"
LAST_FULL_YEAR=datetime.now(timezone.utc).year-1

def normalize(v):
    v=unicodedata.normalize("NFD",str(v).lower())
    return "".join(c for c in v if unicodedata.category(c)!="Mn")

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current=None
        self.text=[]
        self.candidates=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.current=dict(attrs).get("href")
            self.text=[]
    def handle_data(self,data):
        if self.current is not None:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.current is not None:
            name=normalize(" ".join(self.text))
            if "frota por munic" in name and "tipo" in name:
                self.candidates.append((name,self.current))
            self.current=None
            self.text=[]

def download(url,limit,accepted):
    if urllib.parse.urlsplit(url).scheme!="https" or urllib.parse.urlsplit(url).hostname!="www.gov.br":
        raise ValueError("Fonte externa não é o portal oficial gov.br")
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 MaricaWiki-Observatorio/1.0","Accept":accepted})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=45) as res:
                final=urllib.parse.urlsplit(res.geturl())
                if final.scheme!="https" or final.hostname!="www.gov.br":raise ValueError("Redirecionamento não oficial")
                blob=res.read(limit+1)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (408,429,500,502,503,504) or attempt==2:raise
            print("SENATRAN_RETRY",attempt+1,"HTTP",exc.code,flush=True)
        except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
            if attempt==2:raise
            print("SENATRAN_RETRY",attempt+1,type(exc).__name__,flush=True)
        time.sleep(3*(attempt+1))
    if not 1_000<len(blob)<=limit:
        raise ValueError(f"Arquivo sem tamanho válido: {url} ({len(blob)})")
    return blob

def official_december(year):
    page_url=BASE+str(year)
    page=download(page_url,2_000_000,"text/html,*/*")
    parser=Links()
    parser.feed(page.decode("utf-8",errors="replace"))
    if not parser.candidates:
        raise ValueError(f"Portal SENATRAN sem link de frota municipal e tipo: {year}")
    # Na página de cada ano, as competências aparecem em ordem decrescente;
    # o primeiro link é dezembro. Conferimos também o cabeçalho do XLSX.
    name,href=parser.candidates[0]
    url=urllib.parse.urljoin(page_url,href)
    if urllib.parse.urlsplit(url).hostname!="www.gov.br":
        raise ValueError(f"Planilha externa ao portal oficial: {year}")
    return read_official_file(year,page_url,url)

def read_official_file(year,page_url,url):
    blob=download(url,15_000_000,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
    original_sha=sha256(blob).hexdigest()
    if zipfile.is_zipfile(io.BytesIO(blob)):
        total,header=parse_xlsx(blob,year)
    else:
        if blob.startswith(b"Rar!"):
            blob=extract_rar(blob,year)
        if not blob.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
            raise ValueError(f"Formato oficial não suportado: {year}")
        total,header=parse_xls(blob,year)
    return {"ano":str(year),"frota":total,"pagina":page_url,"arquivo":url,
            "sha256":original_sha,"cabecalho_planilha":header}


def extract_rar(blob,year):
    """Descompacta exclusivamente um XLS/XLSX presente em RAR de fonte gov.br."""
    if shutil.which("7z") is None:
        raise ValueError("7z não instalado; impossível auditar a fonte RAR")
    with tempfile.TemporaryDirectory(prefix="senatran_") as directory:
        path=Path(directory)/("frota-"+str(year)+".rar")
        path.write_bytes(blob)
        listing=subprocess.run(["7z","l","-slt",str(path)],capture_output=True,text=True,timeout=35,check=True)
        names=re.findall(r"^Path = (.+\.(?:xls|xlsx))$",listing.stdout,flags=re.I|re.M)
        if len(names)!=1:
            raise ValueError(f"RAR deve conter um único Excel: {year}; identificados {names}")
        extracted=subprocess.run(["7z","x","-so",str(path),names[0]],stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,timeout=35,check=True)
        result=extracted.stdout
        if not 20_000<len(result)<15_000_000:
            raise ValueError(f"XLS extraído do RAR com tamanho anômalo em {year}")
        print("RAR",year,"entrada",names[0],"bytes",len(result),flush=True)
        return result


def parse_xls(blob,year):
    """Lê a tabela municipal do legado XLS Excel 97–2003."""
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("Leitor XLS 97-2003 ausente na rotina de auditoria") from exc
    workbook=xlrd.open_workbook(file_contents=blob,on_demand=True)
    matches=[]
    headers=[]
    for sheet in workbook.sheets():
        print("XLS",year,"aba",sheet.name,"linhas",sheet.nrows,"colunas",sheet.ncols,flush=True)
        for rownum in range(sheet.nrows):
            row=sheet.row_values(rownum)
            if rownum<8:
                headers.extend(str(x) for x in row[:8] if "frota" in normalize(x))
            if len(row)<4:continue
            if normalize(row[0]).strip()=="rj" and normalize(row[1]).strip()=="marica":
                matches.append(row)
    if len(matches)!=1:
        raise ValueError(f"XLS {year} sem linha única de Maricá/RJ: {len(matches)}")
    values=matches[0]
    if not isinstance(values[2],(float,int)) or int(values[2])!=values[2]:
        raise ValueError(f"Frota não inteira no XLS {year}: {values[2]!r}")
    total=int(values[2])
    components=[int(x) for x in values[3:] if isinstance(x,(float,int)) and x==int(x)]
    if not 5000<total<500000 or sum(components)!=total:
        raise ValueError(f"Total XLS inválido ou categorias divergentes em {year}: {total}, {sum(components)}")
    valid=[x for x in headers if str(year) in x and "dez" in normalize(x)]
    if not valid:
        raise ValueError(f"Sem referência a dezembro/{year} na planilha XLS: {headers[:8]}")
    return total,valid[0]


def parse_xlsx(blob,year):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=z.namelist()
        if "xl/sharedStrings.xml" not in names:
            raise ValueError(f"XLSX {year} sem strings compartilhadas")
        shared=[]
        with z.open("xl/sharedStrings.xml") as fh:
            for _,e in ET.iterparse(fh,events=("end",)):
                if e.tag==NAMESPACE+"si":
                    shared.append("".join(v.text or "" for v in e.iter(NAMESPACE+"t")))
                    e.clear()
        sheets=[n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",n)]
        if not sheets:raise ValueError("Planilha sem abas tabulares")
        headers=[]
        matches=[]
        for sheet in sheets:
            with z.open(sheet) as fh:
                for _,row in ET.iterparse(fh,events=("end",)):
                    if row.tag!=NAMESPACE+"row":continue
                    cells={}
                    for c in row.iter(NAMESPACE+"c"):
                        pos=re.match("[A-Z]+",c.get("r",""))
                        if not pos:continue
                        v=c.find(NAMESPACE+"v")
                        inline=c.find(NAMESPACE+"is")
                        val=(v.text or "") if v is not None else "".join(t.text or "" for t in inline.iter(NAMESPACE+"t")) if inline is not None else ""
                        if c.get("t")=="s" and val!="":
                            val=shared[int(val)]
                        cells[pos.group(0)]=val
                    header=cells.get("A","")
                    if "frota de veiculos" in normalize(header):
                        headers.append(str(header))
                    if normalize(cells.get("A","")).strip()=="rj" and normalize(cells.get("B","")).strip()=="marica":
                        matches.append(cells)
                    row.clear()
        if len(matches)!=1:
            raise ValueError(f"Esperada 1 linha MARICA/RJ ({year}); encontradas {len(matches)}")
        valid_headers=[v for v in headers if str(year) in v and re.search(r"dez",normalize(v))]
        if not valid_headers:
            raise ValueError(f"A planilha selecionada não corresponde a dezembro/{year}: {headers}")
        rec=matches[0]
        if not re.fullmatch(r"[0-9]+",rec.get("C","")):
            raise ValueError("Frota total não é inteiro")
        total=int(rec["C"])
        # Somatório dos tipos D:X, sem utilizar subtotais de outros municípios.
        categories=[int(v) for c,v in rec.items() if re.fullmatch(r"[D-Z]+",c) and re.fullmatch("[0-9]+",v)]
        if not 5_000 < total < 500_000 or sum(categories)!=total:
            raise ValueError(f"Inconsistência nos veículos por tipo em Maricá/{year}: {total} vs {sum(categories)}")
        return total,valid_headers[0]

def load_validated_fleet():
    raw=json.loads(FROTA.read_text(encoding="utf-8"))
    values=raw["serie"]
    years=[int(x["ano"]) for x in values]
    if not years or years!=list(range(2014,years[-1]+1)) or years[-1]>LAST_FULL_YEAR:
        raise ValueError("Cache de frota descontínuo ou futuro")
    for x in values:
        if not re.fullmatch(r"[a-f0-9]{64}",x["sha256"]) or not 5000<x["frota"]<500000:
            raise ValueError("Cache inválido")
        for key in ("pagina","arquivo"):
            url=urllib.parse.urlsplit(x[key])
            if url.scheme!="https" or url.hostname!="www.gov.br":
                raise ValueError("Cache sem fonte oficial")
        if str(x["ano"]) not in x["cabecalho_planilha"] or "dez" not in normalize(x["cabecalho_planilha"]):
            raise ValueError("Cache sem dezembro confirmado")
    return values

def fetch_fleet(cache=False,full=False):
    values=load_validated_fleet()
    if cache:return values
    if full:
        return [official_december(y) for y in range(2014,LAST_FULL_YEAR+1)]
    # Revalidar apenas o último exercício publicado e obter exercícios novos.
    # O histórico auditado não precisa ser baixado a cada execução.
    last=values[-1]
    year=int(last["ano"])
    print("SENATRAN_REVALIDAR",year,last["arquivo"],flush=True)
    latest=read_official_file(year,last["pagina"],last["arquivo"])
    result=values[:-1]+[latest]
    for y in range(year+1,LAST_FULL_YEAR+1):
        result.append(official_december(y))
    return result

def years_for_indicator(code,last_year):
    info=json.loads((DATA/(code+".json")).read_text(encoding="utf-8"))
    if info["id"]!=code or info["fonte"]["url"]!="https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv":
        raise ValueError(f"Numerador não é a fonte oficial ISP: {code}")
    raw=info["serie"]
    values={}
    for item in raw:
        key=item["competencia"]
        if re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])",key) and 2014<=int(key[:4])<=last_year:
            values.setdefault(key[:4],[]).append((key,int(item["registros"])))
    count={}
    for year in range(2014,last_year+1):
        items=values.get(str(year),[])
        if sorted(m for m,_ in items)!=[f"{year}-{month:02d}" for month in range(1,13)]:
            raise ValueError(f"Faltam competências oficiais para {code} em {year}")
        count[str(year)]=sum(v for _,v in items)
    return count,info["fonte"]

def validate_proposal(files,changed):
    # Inclui manifestos dos dois lotes que consomem a frota.
    result={name:files[name].encode("utf-8") for name in changed}
    for filename in ("lote-01.manifest.json","lote-06.manifest.json"):
        manifest=json.loads((DATA/filename).read_text(encoding="utf-8"))
        touched=False
        for group in (manifest["files"],manifest.get("dependencias",{})):
            for name,raw in result.copy().items():
                if name in group:
                    group[name]=git_blob(raw)
                    touched=True
        if touched:result[filename]=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="senatran_proposta_") as temp:
        root=Path(temp)
        shutil.copytree(DATA,root/"observatorio")
        (root/"scripts").mkdir()
        for name,raw in result.items():
            (root/"observatorio"/name).write_bytes(raw)
        for filename in ("validar_lote_01.py","validar_lote_06.py"):
            dest=root/"scripts"/filename
            shutil.copy2(ROOT/"scripts"/filename,dest)
            subprocess.run([sys.executable,str(dest)],check=True)
    return result

def git_blob(data):
    # Os manifestos usam o SHA-1 de blobs Git; o SHA-256 da fonte permanece separado.
    import hashlib
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--usar-cache",action="store_true")
    p.add_argument("--auditoria-completa",action="store_true",help="Reconsultar todos os exercícios históricos")
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    if args.usar_cache and args.auditoria_completa:p.error("Modos incompatíveis")
    fleet=fetch_fleet(cache=args.usar_cache,full=args.auditoria_completa)
    years=[int(r["ano"]) for r in fleet]
    if years!=list(range(2014,years[-1]+1)) or years[-1]>LAST_FULL_YEAR:
        raise ValueError("Frota incompleta ou fora do período")
    old=json.loads(FROTA.read_text(encoding="utf-8"))
    files={}
    changed=[]
    if fleet!=old["serie"]:
        changed.append(FROTA.name)
        old["serie"]=fleet
        old["titulo"]=f"Frota municipal Maricá, dezembro 2014–{years[-1]}"
    files[FROTA.name]=json.dumps(old,ensure_ascii=False,indent=2)+"\n"
    files["FROTA-MARICA-ANUAL.csv"]="ano;veiculos_registrados\n"+"".join(f'{r["ano"]};{r["frota"]}\n' for r in fleet)
    for code,_,_,_ in SPEC:
        counts,source=years_for_indicator(code,years[-1])
        series=[]
        for r in fleet:
            year=r["ano"]; n=counts[year]; f=r["frota"]
            if not 5000<f<500000:raise ValueError("Denominador anômalo")
            rate=(Decimal(n)*Decimal(100000)/Decimal(f)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
            series.append({"ano":year,"casos":n,"frota":f,"taxa_por_100_mil_veiculos":str(rate)})
        name=code+"-taxa-frota.json"
        payload=json.loads((DATA/name).read_text(encoding="utf-8"))
        refs=[{"ano":x["ano"],"url":x["arquivo"],"sha256":x["sha256"]} for x in fleet]
        if payload["serie"]!=series or payload["fonte_registros_isp"]!=source or payload["fonte_frota_senatran"]!=refs:
            changed.append(name)
            payload.update(serie=series,fonte_registros_isp=source,fonte_frota_senatran=refs)
        files[name]=json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
        files[code+"-taxa-frota.csv"]="ano;casos_isp;frota_renavam;taxa_por_100_mil_veiculos\n"+"".join(f'{r["ano"]};{r["casos"]};{r["frota"]};{r["taxa_por_100_mil_veiculos"].replace(".",",")}\n' for r in series)
    for name,raw in files.items():
        if name.endswith(".csv") and raw!=(DATA/name).read_bytes().decode("utf-8"):
            changed.append(name)
    if changed:
        if args.usar_cache:raise SystemExit("SENATRAN_REVISAR: divergência na base offline")
        proposal=validate_proposal(files,changed)
        if args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora do repositório")
            out.mkdir(parents=True,exist_ok=False)
            for name,raw in proposal.items():(out/name).write_bytes(raw)
        print("SENATRAN_PROPOSTA: revisão necessária;",len(proposal),"arquivos, sem publicar",flush=True)
        return
    print("SENATRAN_OK:",len(years),"anos; três taxas conciliadas; sem dados de efetivo policial")

if __name__=="__main__":
    main()

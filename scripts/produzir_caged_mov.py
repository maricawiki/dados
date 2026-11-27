#!/usr/bin/env python3
"""Novo Caged MOV: atualização de competências novas, sem FOR/EXC.

Nenhum microdado é impresso, anexado ou versionado. A série ONMT é independente.
A conexão FTP oficial é legada; SHA-256 registra o arquivo recebido, não substitui
uma assinatura do emissor. Novos valores exigem revisão antes de publicar.
"""
import argparse
import csv
import ftplib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
FTP_ROOT="/pdet/microdados/NOVO CAGED"
HOST="ftp.mtps.gov.br"
CITY="330270"
MAX_PACKED=200_000_000
MAX_RAW=1_500_000_000
FIELDS=("admissoes","desligamentos","saldo")
ORIGIN="MTE_CAGEDMOV_SEM_AJUSTES"
DATE=datetime.now(timezone.utc).date().isoformat()
RUN=os.environ.get("GITHUB_RUN_ID")

def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def encode(x):return (json.dumps(x,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def norm(x):return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",x).encode("ascii","ignore").decode().lower())
def month_after(comp):
    y,m=map(int,comp.split("-"))
    return f"{y+int(m==12)}-{m%12+1:02d}"
def remote_path(comp):
    y,m=comp.split("-")
    token=y+m
    return f"{FTP_ROOT}/{y}/{token}/CAGEDMOV{token}.7z"

def parse_rows(raw,comp):
    rdr=csv.DictReader(raw,delimiter=";")
    fields={norm(x):x for x in rdr.fieldnames or []}
    if len(fields)!=len(rdr.fieldnames or []) or not {"municipio","saldomovimentacao","competenciamov"}<=fields.keys():
        raise ValueError("Esquema MOV não reconhecido")
    a=d=0
    for row in rdr:
        if row[fields["municipio"]].strip()!=CITY:continue
        if row[fields["competenciamov"]].strip() not in (comp.replace("-",""),comp[-2:]+"/"+comp[:4]):
            raise ValueError("Competência municipal divergente")
        movement=row[fields["saldomovimentacao"]].strip()
        if movement=="1":a+=1
        elif movement=="-1":d+=1
        else:raise ValueError("Movimento não reconhecido")
    if not (0<a<100000 and 0<d<100000):raise ValueError("Contagens municipais anômalas")
    return {"competencia":comp,"admissoes":a,"desligamentos":d,"saldo":a-d}

def available(ftp,comp):
    y,month=comp.split("-")
    token=y+month
    ftp.cwd(FTP_ROOT)
    if y not in {x.rstrip("/").rsplit("/",1)[-1] for x in ftp.nlst()}:return False
    ftp.cwd(f"{FTP_ROOT}/{y}")
    if token not in {x.rstrip("/").rsplit("/",1)[-1] for x in ftp.nlst()}:return False
    ftp.cwd(f"{FTP_ROOT}/{y}/{token}")
    return f"CAGEDMOV{token}.7z" in {x.rstrip("/").rsplit("/",1)[-1] for x in ftp.nlst()}

def extract(ftp,comp):
    path=remote_path(comp)
    directory,filename=path.rsplit("/",1)
    member="CAGEDMOV"+comp.replace("-","")+".txt"
    with tempfile.TemporaryDirectory(prefix="caged_mov_") as tmp:
        packed=Path(tmp)/filename
        digest=hashlib.sha256()
        size=0
        ftp.cwd(directory)
        with packed.open("wb") as out:
            def receive(chunk):
                nonlocal size
                size+=len(chunk)
                if size>MAX_PACKED:raise ValueError("Pacote acima do limite")
                digest.update(chunk)
                out.write(chunk)
            ftp.retrbinary("RETR "+filename,receive,blocksize=128*1024)
        if size<10000:raise ValueError("Pacote insuficiente")
        # 7z transmite o único TXT esperado por stdout: não extrai caminhos do pacote.
        listing=subprocess.run(["7z","l","-slt",str(packed)],capture_output=True,text=True,timeout=60,check=True).stdout
        entries=listing.split("----------\n",1)
        if len(entries)!=2:raise ValueError("Inventário 7z não reconhecido")
        paths=re.findall(r"^Path = (.+)$",entries[1],re.M)
        sizes=re.findall(r"^Size = (\d+)$",entries[1],re.M)
        if paths!=[member] or len(sizes)!=1 or not 0<int(sizes[0])<=MAX_RAW:
            raise ValueError("Conteúdo de pacote inesperado")
        with subprocess.Popen(["7z","x","-so",str(packed),member],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as proc:
            try:
                with io.TextIOWrapper(proc.stdout,encoding="utf-8-sig",errors="strict",newline="") as raw:
                    counts=parse_rows(raw,comp)
                if proc.wait(timeout=60)!=0:raise ValueError("Descompressão falhou")
            except BaseException:
                proc.kill()
                proc.wait()
                raise
        return counts,{"competencia":comp,"ftp":path,"sha256":digest.hexdigest()}

def quarters(rows):
    result=[]
    for i in range(0,len(rows)-2,3):
        chunk=rows[i:i+3]
        first=chunk[0]["competencia"]
        year,month=map(int,first.split("-"))
        if month not in (1,4,7,10) or [x["competencia"] for x in chunk]!=[first,month_after(first),month_after(month_after(first))]:
            raise ValueError("Trimestre incompleto ou descontínuo")
        q=(month+2)//3
        result.append({"periodo":f"{year}-T{q}","ano":year,"trimestre":q,
                       "meses":"|".join(x["competencia"] for x in chunk),
                       **{field:sum(x[field] for x in chunk) for field in FIELDS}})
    return result

def verify_existing(monthly,quarterly):
    rows=monthly["serie"]
    refs=monthly["fonte"]["arquivos"]
    if monthly["codigo_ibge"]!="3302700" or monthly["fonte"]["tipo_arquivo"]!="CAGEDMOV":
        raise ValueError("Fonte MOV inválida")
    if rows[0]["competencia"]!="2024-01" or len(refs)!=len(rows):raise ValueError("Cobertura original")
    for i,(x,f) in enumerate(zip(rows,refs)):
        comp=x["competencia"]
        if i and comp!=month_after(rows[i-1]["competencia"]):raise ValueError("Lacuna MOV")
        if f["competencia"]!=comp or f["ftp"]!=remote_path(comp) or not re.fullmatch("[0-9a-f]{64}",f["sha256"]):
            raise ValueError("Proveniência inválida")
        if min(x["admissoes"],x["desligamentos"])<0 or x["saldo"]!=x["admissoes"]-x["desligamentos"]:
            raise ValueError("Saldo inválido")
    if quarterly["serie"]!=quarters(rows) or quarterly["fonte"]["arquivos"]!=refs:raise ValueError("Trimestres divergentes")

def build(monthly,quarterly,new):
    rows=monthly["serie"]
    refs=monthly["fonte"]["arquivos"]
    for counts,source in new:
        if counts["competencia"]!=month_after(rows[-1]["competencia"]) or source["competencia"]!=counts["competencia"]:
            raise ValueError("Não preencher lacunas ou sobrescrever competências")
        rows.append(counts)
        refs.append(source)
    if not new:return {}
    quarterly["serie"]=quarters(rows)
    quarterly["fonte"]["arquivos"]=refs
    last=rows[-1]["competencia"]
    for item in (monthly,quarterly):
        item["fonte"]["data_extracao"]=DATE
        if RUN:item["fonte"]["auditorias"].append("https://github.com/maricawiki/dados/actions/runs/"+RUN)
        item["explorador_periodos"]["ultima_competencia_confirmada"]=last
    monthly["observacoes"][0]="Série de 2024-01 a "+last+"; último ano parcial se dezembro não estiver disponível."
    quarterly["observacoes"][0]="Somente trimestres completos: "+quarterly["serie"][0]["periodo"]+" a "+quarterly["serie"][-1]["periodo"]+"."
    verify_existing(monthly,quarterly)
    a=io.StringIO(newline="")
    w=csv.writer(a,lineterminator="\n")
    w.writerow(("competencia",*FIELDS,"fonte","sha256_arquivo"))
    for x,f in zip(rows,refs):w.writerow((x["competencia"],*(x[k] for k in FIELDS),ORIGIN,f["sha256"]))
    b=io.StringIO(newline="")
    w=csv.writer(b,lineterminator="\n")
    w.writerow(("trimestre",*FIELDS,"meses_incluidos","fonte"))
    for x in quarterly["serie"]:w.writerow((x["periodo"],*(x[k] for k in FIELDS),x["meses"],ORIGIN))
    return {"TRB-001.json":encode(monthly),"TRB-002.json":encode(quarterly),
            "TRB-001.csv":a.getvalue().encode(),"TRB-002.csv":b.getvalue().encode()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--somente-revalidar",action="store_true")
    p.add_argument("--propor",type=Path)
    args=p.parse_args()
    monthly=json.loads((DATA/"TRB-001.json").read_text(encoding="utf-8"))
    quarterly=json.loads((DATA/"TRB-002.json").read_text(encoding="utf-8"))
    verify_existing(monthly,quarterly)
    last=monthly["serie"][-1]
    ref=monthly["fonte"]["arquivos"][-1]
    new=[]
    with ftplib.FTP(encoding="latin-1",timeout=85) as ftp:
        ftp.connect(HOST,21)
        ftp.login()
        ftp.sendcmd("TYPE I")
        old,source=extract(ftp,last["competencia"])
        if old!=last or source!=ref:raise ValueError("Último MOV retificado: revisar recortes dependentes e não atualizar automaticamente")
        print("CAGED_REVALIDADO",last["competencia"],flush=True)
        if not args.somente_revalidar:
            current=month_after(last["competencia"])
            # Até três competências novas por execução; não considerar mês em curso.
            for _ in range(3):
                if current>=date.today().strftime("%Y-%m") or not available(ftp,current):
                    print("CAGED_AGUARDAR",current,flush=True)
                    break
                counts,source=extract(ftp,current)
                new.append((counts,source))
                current=month_after(current)
    changed=build(monthly,quarterly,new)
    if changed:
        name="lote-03.manifest.json"
        manifest=json.loads((DATA/name).read_text(encoding="utf-8"))
        for filename,raw in changed.items():manifest["files"][filename]=blob(raw)
        changed[name]=encode(manifest)
        with tempfile.TemporaryDirectory(prefix="validar_caged_") as tmp:
            root=Path(tmp)
            shutil.copytree(DATA,root/"observatorio")
            (root/"scripts").mkdir()
            for filename,raw in changed.items():(root/"observatorio"/filename).write_bytes(raw)
            test=root/"scripts/validar_lote_03.py"
            shutil.copy2(ROOT/"scripts"/test.name,test)
            subprocess.run([sys.executable,str(test)],check=True)
        if args.propor:
            out=args.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora da árvore")
            out.mkdir(parents=True,exist_ok=False)
            for filename,raw in changed.items():(out/filename).write_bytes(raw)
    print("CAGED_PROPOSTA",len(new),"meses;",len(changed),"arquivos; sem publicar",flush=True)

if __name__=="__main__":main()

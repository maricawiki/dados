#!/usr/bin/env python3
"""Consolida somente artefatos agregados dos produtores autorizados.

Não executa conteúdo de artefato. A origem (repo/branch/evento/SHA) é
validada no workflow. Propostas concorrentes não podem sobrescrever main.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
MANIFEST=re.compile(r"lote-0[1-6]\.manifest\.json")
MAX_FILE=5_000_000
SOURCES={
 "Propor estatísticas vitais SES-RJ (sem publicar)":("vitais-proposta",),
 "Propor PIB municipal SIDRA (sem publicar)":("pib-proposta",),
 "Propor Novo Caged MOV municipal (sem publicar)":("caged-mov-proposta",),
 "Validar e propor DCA integral (sem publicar)":("dca-integral-proposta",),
 "Monitorar fontes ISP-RJ (sem publicar)":("isp-registros-proposta","isp-taxas-proposta"),
 "Conferir fonte oficial SENATRAN (sem publicar)":("senatran-proposta",),
 "Validar produtores CEMPRE CNAE e leitos CNES (sem publicar)":("cnae-proposta","leitos-proposta"),
}
RULES={
 "vitais-proposta":(r"SAU-00[45]\.(?:csv|json)",("04",)),
 "pib-proposta":(r"ECO-001\.(?:csv|json)",("03",)),
 "caged-mov-proposta":(r"TRB-00[12]\.(?:csv|json)",("03",)),
 "dca-integral-proposta":(r"FIN-0(?:0[1-9]|1[0-7])\.(?:csv|json)",("02",)),
 "isp-registros-proposta":(r"SEG-0(?:0[1-9]|[1-4][0-9]|5[01])(?:-taxa-frota)?\.(?:csv|json)",("06",)),
 "isp-taxas-proposta":(r"SEG-0(?:0[1-9]|[1-4][0-9]|5[01])-(?:taxas\.json|taxa-(?:anual|mensal)\.csv)",("06",)),
 "senatran-proposta":(r"(?:FROTA-MARICA-ANUAL|SEG-(?:002|014|023)-taxa-frota)\.(?:csv|json)",("01","06")),
 "cnae-proposta":(r"ECO-005\.(?:csv|json)",("03",)),
 "leitos-proposta":(r"SAU-002\.(?:csv|json)",("04",)),
}

def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def encode(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def load_bytes(path):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_FILE:
        raise ValueError("Arquivo de artefato inválido: "+path.name)
    raw=path.read_bytes()
    raw.decode("utf-8")
    return raw
def groups(m):return ("files","dependencias") if "dependencias" in m else ("files",)

def collect(folder,source,data=DATA):
    if source not in SOURCES:raise ValueError("Workflow fonte não autorizado")
    if folder.is_symlink() or not folder.is_dir():raise ValueError("Pasta de artefatos inválida")
    original={f.name:json.loads(f.read_text(encoding="utf-8")) for f in data.glob("lote-*.manifest.json")}
    result={}
    touched=set()
    for directory in sorted(folder.iterdir()):
        if directory.name not in SOURCES[source] or directory.is_symlink() or not directory.is_dir():
            raise ValueError("Artefato não autorizado: "+directory.name)
        pattern,lots=RULES[directory.name]
        candidate={}
        manifests={}
        for path in sorted(directory.iterdir()):
            raw=load_bytes(path)
            if MANIFEST.fullmatch(path.name):
                if path.name not in {f"lote-{i}.manifest.json" for i in lots}:raise ValueError("Manifesto fora do escopo")
                manifests[path.name]=json.loads(raw)
            elif re.fullmatch(pattern,path.name):
                candidate[path.name]=raw
            else:raise ValueError("Arquivo fora do escopo: "+path.name)
        if not candidate or not manifests:raise ValueError("Artefato sem dados ou manifesto")
        covered=set()
        for name,manifest in manifests.items():
            old=original[name]
            # Manter rigorosamente as chaves e valores não alterados.
            expected=json.loads(json.dumps(old))
            for group in groups(old):
                for filename in old[group]:
                    if filename in candidate:
                        expected[group][filename]=blob(candidate[filename])
                        covered.add(filename)
            if manifest!=expected:raise ValueError("Manifesto não concilia com artefato: "+name)
            touched.add(name)
        if set(candidate)!=covered:raise ValueError("Dados sem manifesto correspondente")
        for name,raw in candidate.items():
            if not (data/name).is_file():raise ValueError("Novo arquivo fora do inventário "+name)
            if name in result and result[name]!=raw:raise ValueError("Propostas conflitantes "+name)
            if raw!=(data/name).read_bytes():result[name]=raw
    # Um arquivo compartilhado (frota) precisa manter todos os manifestos coerentes.
    for name,old in original.items():
        changed=False
        for group in groups(old):
            for filename in old[group]:
                if filename in result:
                    if name not in touched:raise ValueError("Manifesto dependente ausente "+name)
                    old[group][filename]=blob(result[filename])
                    changed=True
        if changed:result[name]=encode(old)
    return result

def check(root):
    for name in ("validar_lote_01.py","validar_lote_02.py","validar_financas_conciliacao.py",
                 "validar_lote_03.py","validar_lote_04.py","validar_lote_05.py","validar_lote_06.py",
                 "validar_dair_detalhes.py"):
        subprocess.run([sys.executable,str(root/"scripts"/name)],check=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artefatos",type=Path,required=True)
    p.add_argument("--fonte",required=True)
    p.add_argument("--aplicar",action="store_true")
    args=p.parse_args()
    result=collect(args.artefatos,args.fonte)
    if result:
        with tempfile.TemporaryDirectory(prefix="validacao_proposta_") as tmp:
            root=Path(tmp)
            shutil.copytree(DATA,root/"observatorio")
            shutil.copytree(ROOT/"scripts",root/"scripts",ignore=shutil.ignore_patterns("__pycache__"))
            for name,raw in result.items():(root/"observatorio"/name).write_bytes(raw)
            check(root)
        if args.aplicar:
            for name,raw in result.items():(DATA/name).write_bytes(raw)
    print("PROPOSTA_PUBLICA",len(result),"arquivos revisáveis; nunca publicar automaticamente",flush=True)

if __name__=="__main__":main()

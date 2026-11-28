#!/usr/bin/env python3
"""Propostas coordenadas ECO-008/009/010, estoques oficiais SIMEI/SINAC.
Somente exercícios encerrados já homologados; extensão exige revisar fichas.
"""
import argparse,csv,hashlib,io,json,shutil,subprocess,sys,tempfile
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from receita_simei_sinac_fonte import city_id,fetch_year,extract_year,simei_url,sinac_url,urllib,http
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"observatorio"
IDS=("ECO-008","ECO-009","ECO-010")
FIELDS={
 "ECO-008":("ano","valor","data_referencia","posicao_consolidada","municipio_sinac","fonte"),
 "ECO-009":("ano","variacao_percentual","meis_ano","meis_ano_anterior","status","data_referencia","fonte"),
 "ECO-010":("ano","valor","data_referencia","posicao_consolidada","municipio_sinac","fonte"),
}
def load(name):return json.loads((DATA/name).read_text(encoding="utf-8"))
def encode(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode()
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def serialize(code,rows):
    out=io.StringIO(newline="")
    w=csv.writer(out,delimiter=";",lineterminator="\n")
    w.writerow(FIELDS[code])
    for row in rows:
        w.writerow([row["valor"] if k=="variacao_percentual" else row[k] for k in FIELDS[code]])
    return out.getvalue().encode()
def growth(rows):
    out=[]
    previous=None
    for r in rows:
        n=r["valor"];y=r["ano"]
        v=str((Decimal(n-previous)/Decimal(previous)*100).quantize(Decimal(".000001"),rounding=ROUND_HALF_UP)) if previous is not None else None
        out.append({"ano":y,"valor":v,"meis_ano":n,"meis_ano_anterior":previous,"data_referencia":r["data_referencia"],"status":"sem_ano_anterior" if previous is None else "variacao_observada_requer_cautela" if y==2023 else "calculada","fonte":r["fonte"]})
        previous=n
    return out
def verify(stocks,sinac):
    for rows,start,url in ((stocks,2010,simei_url),(sinac,2007,sinac_url)):
        if [r["ano"] for r in rows]!=list(range(start,2026)):raise ValueError("Cobertura divergente; revisão editorial necessária")
        for r in rows:
            y=r["ano"]
            if r["municipio_sinac"]!="5853" or r["data_referencia"]!=f"31/12/{y}" or r["fonte"]!=url(y) or type(r["valor"]) is not int or r["valor"]<=0 or not r["posicao_consolidada"].startswith("Posição Consolidada"):
                raise ValueError("Registro oficial inválido")
    all_s={r["ano"]:r["valor"] for r in sinac}
    for r in stocks:
        if all_s[r["ano"]]<r["valor"]:raise ValueError("Simples Nacional deve incluir SIMEI")
def reference():
    meta={k:load(k+".json") for k in IDS}
    for k,m in meta.items():
        if m["id"]!=k or m["codigo_ibge"]!="3302700" or m["municipio_sinac"]!="5853":raise ValueError("Município divergente")
        if serialize(k,m["serie"])!=(DATA/(k+".csv")).read_bytes():raise ValueError("CSV/JSON divergentes "+k)
    verify(meta["ECO-008"]["serie"],meta["ECO-010"]["serie"])
    if growth(meta["ECO-008"]["serie"])!=meta["ECO-009"]["serie"]:raise ValueError("Taxa histórica divergente")
    return meta
def propose(updates):
    meta=reference()
    revised={}
    for k in ("ECO-008","ECO-010"):
        prior={r["ano"]:r for r in meta[k]["serie"]}
        for r in updates.get(k,[]):
            y=r["ano"]
            if y not in prior:raise ValueError("Novo exercício requer homologação")
            # Data de consolidação isolada não altera a série nem gera PR.
            if prior[y]["valor"]!=r["valor"]:prior[y]=r
        revised[k]=[prior[y] for y in sorted(prior)]
    verify(revised["ECO-008"],revised["ECO-010"])
    revised["ECO-009"]=growth(revised["ECO-008"])
    changes={}
    for k,rows in revised.items():
        if rows!=meta[k]["serie"]:
            meta[k]["serie"]=rows
            changes[k+".csv"]=serialize(k,rows)
            changes[k+".json"]=encode(meta[k])
    if changes:
        m=load("lote-03.manifest.json")
        for n,raw in changes.items():m["files"][n]=blob(raw)
        changes["lote-03.manifest.json"]=encode(m)
    return changes
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--auditoria-completa",action="store_true")
    p.add_argument("--propor",type=Path)
    a=p.parse_args()
    meta=reference()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    city=city_id(opener)
    updates={}
    for k,fn in (("ECO-008",fetch_year),("ECO-010",extract_year)):
        selected=[r["ano"] for r in meta[k]["serie"]] if a.auditoria_completa else [2025]
        updates[k]=[fn(opener,y,city) for y in selected]
        print("RECEITA_REVALIDACAO",k,[(x["ano"],x["valor"]) for x in updates[k]],flush=True)
    changes=propose(updates)
    if changes:
        with tempfile.TemporaryDirectory(prefix="receita_proposta_") as tmp:
            root=Path(tmp)
            shutil.copytree(DATA,root/"observatorio")
            (root/"scripts").mkdir()
            for n,raw in changes.items():(root/"observatorio"/n).write_bytes(raw)
            for n in ("validar_lote_03.py","produzir_simei_sinac.py","receita_simei_sinac_fonte.py"):shutil.copy2(ROOT/"scripts"/n,root/"scripts"/n)
            subprocess.run([sys.executable,str(root/"scripts/validar_lote_03.py")],check=True)
            subprocess.run([sys.executable,"-c","from produzir_simei_sinac import reference; reference()"],cwd=root/"scripts",check=True)
        if a.propor:
            out=a.propor.resolve()
            if out==ROOT or ROOT in out.parents:raise ValueError("Proposta fora da árvore")
            out.mkdir(parents=True,exist_ok=False)
            for n,raw in changes.items():(out/n).write_bytes(raw)
    print("RECEITA_PROPOSTA",len(changes),"arquivos; sem publicar",flush=True)
if __name__=="__main__":main()

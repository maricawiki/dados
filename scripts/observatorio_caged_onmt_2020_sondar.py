#!/usr/bin/env python3
"""Diagnóstico de série histórica do Novo Caged no painel ONMT/MTE.

Acesso somente a agregados de um espelho independente do painel MTE. Não são
microdados e NÃO serão misturados aos CAGEDMOV municipais sem ajustes já
publicados antes da conciliação metodológica. O arquivo Parquet é temporário.
"""
from hashlib import sha256
from pathlib import Path
import csv
import tempfile
import urllib.request
import duckdb

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT/"observatorio/TRB-001.csv"
URL="https://github.com/jtrecenti/painel-onmt/releases/download/dados-2026-09-02/caged.parquet"
MAX_BYTES=140_000_000

def download(path):
    request=urllib.request.Request(URL,headers={
        "User-Agent":"MaricaWiki-Auditoria/1.0","Accept":"application/octet-stream,*/*"})
    digest=sha256();size=0
    with urllib.request.urlopen(request,timeout=160) as res, path.open("wb") as fh:
        while chunk:=res.read(4_194_304):
            size+=len(chunk)
            if size>MAX_BYTES:raise ValueError("Arquivo ONMT maior que limite")
            digest.update(chunk);fh.write(chunk)
    if size<5_000_000:raise ValueError("Arquivo insuficiente")
    print("ONMT_CAGED_ARQUIVO",size,digest.hexdigest(),URL,flush=True)

def main():
    import json
    with tempfile.TemporaryDirectory(prefix="marica_onmt_caged_") as td:
        path=Path(td)/"caged.parquet"
        download(path)
        con=duckdb.connect()
        p=str(path)
        cols=con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[p]).fetchall()
        print("ONMT_CAGED_COLUNAS",[(r[0],r[1]) for r in cols],flush=True)
        names={r[0] for r in cols}
        if "codigo_ibge" not in names:
            print("AVISO: base sem municipio; interrompendo sondagem",flush=True)
            return
        months=con.execute("SELECT MIN(period),MAX(period),COUNT(DISTINCT period) FROM read_parquet(?) WHERE codigo_ibge='330270'",[p]).fetchone()
        print("ONMT_CAGED_PERIODO_MARICA",months,flush=True)
        variables=con.execute("SELECT variaveis,COUNT(*) FROM read_parquet(?) WHERE codigo_ibge='330270' GROUP BY variaveis ORDER BY variaveis",[p]).fetchall()
        print("ONMT_CAGED_VARIAVEIS_MARICA",variables[:120],flush=True)
        samples=con.execute("SELECT * FROM read_parquet(?) WHERE codigo_ibge='330270' LIMIT 8",[p]).fetchall()
        print("ONMT_CAGED_AMOSTRAS_AGREGADAS",samples,flush=True)
        if "tipo_abertura.1" in names:
            details=con.execute('''SELECT variaveis,"tipo_abertura.1","tipo_abertura.2",
                     COUNT(*) FROM read_parquet(?)
                     WHERE codigo_ibge='330270'
                     GROUP BY 1,2,3 ORDER BY 1,2,3''',[p]).fetchall()
            print("ONMT_CAGED_RECORTES",details[:120],flush=True)
        split=con.execute("""
          SELECT tipo_abertura,abertura,variaveis,COUNT(*)
          FROM read_parquet(?)
          WHERE codigo_ibge=330270 AND variaveis IN ('tx_caged_emp_formal','tx_caged_saldo')
          GROUP BY 1,2,3 ORDER BY 3,1,2
        """,[p]).fetchall()
        print("ONMT_CAGED_UNIDADES",split[:120],flush=True)
        checks=con.execute("""
          SELECT period,tipo_abertura,abertura,mensal
          FROM read_parquet(?)
          WHERE codigo_ibge=330270 AND variaveis IN ('tx_caged_emp_formal','tx_caged_saldo')
            AND period IN (DATE '2024-01-01',DATE '2024-12-01',DATE '2025-12-01',DATE '2026-07-01')
            AND abertura='Total'
          ORDER BY period,tipo_abertura
        """,[p]).fetchall()
        print("ONMT_CAGED_COMPARAR_MENSAL",checks,flush=True)
        with REFERENCE.open(encoding="utf-8",newline="") as fh:
            prior=list(csv.DictReader(fh))
        print("REFERENCIA_CAGEDMOV_SEM_AJUSTES",[r for r in prior if r["competencia"] in ("2024-01","2024-12","2025-12","2026-09")],flush=True)
        print("PENDENTE: verificar unidade, período, MOV/FOR/EXC e diferença com 33 meses antes de publicar")

if __name__=="__main__":
    main()

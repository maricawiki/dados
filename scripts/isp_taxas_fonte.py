#!/usr/bin/env python3
"""Integra taxas municipais OFICIAIS ISP-RJ, sem calcular denominadores ou extrapolar anos.

As taxas mensais não são somadas para obter taxa anual. A base anual é outra
fonte publicada pelo ISP-RJ e pode estar desatualizada em relação à mensal.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from observatorio_isp_download import download
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path

from isp_registros_fonte import SPEC, SERIES_START

URL = {
    "mensal": "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioTaxaMes.csv",
    "anual": "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioTaxaAno.csv",
}
BEGIN = "<!-- INICIO TAXAS OFICIAIS ISP-RJ -->"
END = "<!-- FIM TAXAS OFICIAIS ISP-RJ -->"
NOTE_POP = "https://www.ispdados.rj.gov.br/metodologiaCalPopulacao.html"
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _decode(blob):
    for codec in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return blob.decode(codec), codec
        except UnicodeDecodeError:
            continue
    raise ValueError("Codificação ilegível")


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower().strip())
                   if unicodedata.category(c) != "Mn")


def _number(raw, key):
    raw = str(raw or "").strip()
    if raw in ("", "-", "...", "NA", "N/A", ".."):
        return None
    if not re.fullmatch(r"[0-9]+(?:,[0-9]+)?", raw):
        raise ValueError(f"Taxa ISP não numérica em {key}: {raw!r}")
    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"Taxa ISP inválida em {key}: {raw!r}") from None
    if not value.is_finite() or value < 0:
        raise ValueError(f"Taxa negativa/infinita: {key}")
    return format(value, "f")


def _read(periodicidade, local=None):
    if local:
        blob = Path(local).read_bytes()
    else:
        blob = download(URL[periodicidade], 35_000_000, timeout=95)
    if not (30_000 < len(blob) <= 35_000_000):
        raise ValueError(f"Tamanho inesperado da fonte de taxas {periodicidade}: {len(blob)}")
    content, codec = _decode(blob)
    rdr = csv.DictReader(io.StringIO(content), delimiter=";")
    fields = set(rdr.fieldnames or [])
    required = {"fmun_cod", "fmun", "ano"} | ({"mes"} if periodicidade == "mensal" else set())
    if not required <= fields:
        raise ValueError(f"Fonte municipal sem chaves {required-fields}")
    # A base anual oficial não contém a coluna roubo_veiculo na edição verificada.
    known = {field for _, _, _, field in SPEC}
    missing = known - fields
    optional = {"registro_ocorrencias"} | ({"roubo_veiculo"} if periodicidade == "anual" else set())
    if missing - optional:
        raise ValueError(f"Taxas {periodicidade} sem variáveis conhecidas: {sorted(missing - optional)}")
    if "registro_ocorrencias" in missing:
        print(f"::warning::SEG-024: variável registro_ocorrencias ausente na fonte {periodicidade}; preservar série validada.")
    records = {}
    for row in rdr:
        if str(row.get("fmun_cod", "")).strip().replace(".0", "") not in ("330270", "3302700"):
            continue
        if _norm(row.get("fmun", "")) != "marica":
            raise ValueError("Código de Maricá com nome municipal inesperado")
        year = int(row["ano"])
        if periodicidade == "mensal":
            month = int(row["mes"])
            if not 1 <= month <= 12:
                raise ValueError(f"Mês inválido: {month}")
            key = f"{year}-{month:02d}"
        else:
            key = f"{year}"
        if not 2014 <= year <= datetime.now(timezone.utc).year:
            raise ValueError("Ano fora da cobertura possível")
        if key in records:
            raise ValueError(f"Competência ISP duplicada: {key}")
        records[key] = {f: _number(row.get(f), f"{key}/{f}") for f in (known & fields)}
    dates = sorted(records)
    if not dates or dates[0] != ("2014-01" if periodicidade == "mensal" else "2014"):
        raise ValueError(f"Fonte anual/mensal sem início 2014: {periodicidade}")
    minimum = 120 if periodicidade == "mensal" else 7
    if len(dates) < minimum:
        raise ValueError(f"Fonte de taxas insuficiente: {periodicidade}, {len(dates)}")
    if periodicidade == "mensal":
        start_year, start_month = 2014, 1
        expected = []
        while f"{start_year}-{start_month:02d}" <= dates[-1]:
            expected.append(f"{start_year}-{start_month:02d}")
            start_month += 1
            if start_month == 13:
                start_year, start_month = start_year + 1, 1
    else:
        expected = [str(y) for y in range(2014, int(dates[-1]) + 1)]
    if dates != expected:
        raise ValueError(f"Competências ausentes em {periodicidade}: {len(dates)} de {len(expected)}")
    return records, {"url": URL[periodicidade], "sha256": hashlib.sha256(blob).hexdigest(),
                     "encoding": codec, "inicio": dates[0], "fim": dates[-1]}


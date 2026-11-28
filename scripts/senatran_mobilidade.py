"""Leitura das categorias oficiais, reutilizando bytes já baixados pelo produtor SENATRAN."""
from __future__ import annotations
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def normal(v):
    return "".join(c for c in unicodedata.normalize("NFD", str(v).lower())
                   if unicodedata.category(c) != "Mn").strip()


def excel_columns(k):
    v = 0
    for c in k:
        v = v * 26 + ord(c) - 64
    return v - 1


def row_values_xlsx(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as stream:
                for _, e in ET.iterparse(stream, events=("end",)):
                    if e.tag == NS + "si":
                        shared.append("".join(c.text or "" for c in e.iter(NS + "t")))
                        e.clear()
        for sheet in [x for x in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", x)]:
            with z.open(sheet) as stream:
                for _, e in ET.iterparse(stream, events=("end",)):
                    if e.tag != NS + "row":
                        continue
                    cells = {}
                    for c in e.iter(NS + "c"):
                        pos = re.match("[A-Z]+", c.get("r", ""))
                        if not pos:
                            continue
                        v = c.find(NS + "v")
                        inline = c.find(NS + "is")
                        raw = (v.text or "") if v is not None else (
                            "".join(t.text or "" for t in inline.iter(NS + "t"))
                            if inline is not None else "")
                        if c.get("t") == "s" and raw != "":
                            raw = shared[int(raw)]
                        cells[excel_columns(pos.group())] = raw
                    if cells:
                        n = max(cells) + 1
                        yield [cells.get(i, "") for i in range(n)]
                    e.clear()


def row_values_xls(blob):
    import xlrd
    workbook = xlrd.open_workbook(file_contents=blob, on_demand=True)
    for sheet in workbook.sheets():
        for r in range(sheet.nrows):
            yield sheet.row_values(r)


def parse(blob, year, expected):
    if zipfile.is_zipfile(io.BytesIO(blob)):
        records = row_values_xlsx(blob)
    elif blob.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        records = row_values_xls(blob)
    else:
        raise ValueError("Formato de arquivo não reconhecido")

    header = None
    matches = []
    last_header = None
    for row in records:
        if len(row) < 4:
            continue
        if normal(row[0]) == "uf" and normal(row[1]) in ("municipio", "municipios"):
            last_header = row
        if normal(row[0]) == "rj" and normal(row[1]) == "marica":
            matches.append((last_header, row))
    if len(matches) != 1:
        raise ValueError(f"Ano {year}: encontradas {len(matches)} linhas municipais")
    h, data = matches[0]
    if h is None:
        raise ValueError("Cabeçalho de categorias não encontrado")
    from decimal import Decimal
    if Decimal(str(data[2])) != expected:
        raise ValueError(f"Total diverge: {data[2]} != {expected}")
    labels = []
    for i in range(3, max(len(h), len(data))):
        label = str(h[i]).strip() if i < len(h) else ""
        val = data[i] if i < len(data) else ""
        if not label and (str(val).strip() in ("", "0", "0.0")):
            continue
        if not label:
            raise ValueError(f"Tipo sem rótulo: coluna {i+1}")
        try:
            from decimal import Decimal
            numeric = Decimal(str(val or 0))
            if not numeric.is_finite() or numeric != numeric.to_integral_value():
                raise ValueError("Quantidade não inteira")
            number = int(numeric)
        except ValueError as exc:
            raise ValueError(f"Valor inválido: {label} = {val!r}") from exc
        if number < 0:
            raise ValueError("Frota negativa")
        labels.append({"coluna": i + 1, "tipo_oficial": label, "valor": number})
    if not 16 <= len(labels) <= 27 or sum(x["valor"] for x in labels) != expected:
        raise ValueError(f"Categorias {len(labels)}, soma {sum(x['valor'] for x in labels)} diferente de {expected}")
    return labels



def reconcile(data, year, total, digest, blob):
    """Nenhuma revisão de frota isolada pode deixar mobilidade incoerente."""
    historical=json.loads((data/"MOB-004-historico.json").read_text(encoding="utf-8"))
    rows={x["ano"]:x for x in historical["serie"]}
    if year not in rows:
        raise ValueError(f"Novo exercício {year}: requer proposta coordenada MOB-001–009, frota e taxas ISP")
    ref=rows[year]
    if ref["total"]!=total or ref["fonte_sha256"]!=digest:
        raise ValueError(f"Revisão da fonte {year}: reconciliar mobilidade e segurança antes da publicação")
    labels=parse(blob,year,total)
    actual={x["tipo_oficial"]:x["valor"] for x in labels}
    if len(actual)!=len(labels) or actual!=ref["tipos"]:
        raise ValueError(f"Categorias SENATRAN divergentes em {year}: revisão editorial necessária")
    print("MOBILIDADE_FONTE_OK",year,len(actual),"categorias, sem download adicional",flush=True)

def validate_local(data):
    def read(name):return json.loads((data/(name+".json")).read_text(encoding="utf-8"))
    history=read("MOB-004-historico")
    rows={x["ano"]:x for x in history["serie"]}
    fleet={int(x["ano"]):x for x in read("FROTA-MARICA-ANUAL")["serie"]}
    if history["codigo_ibge"]!="3302700" or len(rows)!=len(history["serie"]) or set(rows)!=set(fleet):
        raise ValueError("Cobertura da frota não conciliada")
    for y,r in rows.items():
        if set(r["tipos"])!=set(history["categorias_originais"]) or any(type(n) is not int or n<0 for n in r["tipos"].values()):
            raise ValueError("Categorias inválidas")
        if sum(r["tipos"].values())!=r["total"] or r["total"]!=fleet[y]["frota"] or r["fonte_sha256"]!=fleet[y]["sha256"]:
            raise ValueError("Total ou fonte de frota divergente")
    for code in ("MOB-001","MOB-005","MOB-006","MOB-007","MOB-009"):
        m=read(code)
        if m["codigo_ibge"]!="3302700" or [x["ano"] for x in m["serie"]]!=sorted(rows):
            raise ValueError("Cobertura divergente "+code)
        for x in m["serie"]:
            r=rows[x["ano"]]
            if code=="MOB-001":
                if x["frota"]!=r["total"]:raise ValueError(code)
            elif code=="MOB-009":
                if x["onibus"]!=r["tipos"]["ONIBUS"] or x["micro_onibus_excluidos"]!=r["tipos"]["MICRO-ONIBUS"] or x["frota_total"]!=r["total"]:raise ValueError(code)
            else:
                expected={k:r["tipos"][k] for k in m["categorias_oficiais"]}
                if x["componentes"]!=expected or x["valor"]!=sum(expected.values()) or x["frota_total"]!=r["total"]:raise ValueError(code)
    print("MOBILIDADE_LOCAL_OK",len(rows),"anos e totais de categorias conciliados",flush=True)

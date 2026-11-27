#!/usr/bin/env python3
"""Leitor de registros municipais da fonte oficial ISP-RJ, somente leitura.

O processo falha fechado: se fonte, esquema, cobertura, identificador municipal
ou valores não puderem ser verificados, nenhum arquivo publicado é alterado.
Não cria projeções, zeros artificiais nem taxas com denominadores desconhecidos.
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
from html import escape
from pathlib import Path

URL = "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv"
SPEC = [
    ("SEG-001", "Homicídios dolosos", "homicidios-dolosos", "hom_doloso"),
    ("SEG-002", "Roubos de veículos", "roubos-veiculos", "roubo_veiculo"),
    ("SEG-003", "Latrocínios", "latrocinios", "latrocinio"),
    ("SEG-004", "Mortes por intervenção de agentes do Estado", "mortes-intervencao-estado", "hom_por_interv_policial"),
    ("SEG-005", "Tentativas de homicídio", "tentativas-homicidio", "tentat_hom"),
    ("SEG-006", "Lesões corporais dolosas", "lesoes-corporais-dolosas", "lesao_corp_dolosa"),
    ("SEG-007", "Estupros", "estupros", "estupro"),
    ("SEG-008", "Roubos a transeuntes", "roubos-transeuntes", "roubo_transeunte"),
    ("SEG-009", "Roubos de celulares", "roubos-celulares", "roubo_celular"),
    ("SEG-010", "Roubos em transporte coletivo", "roubos-transporte-coletivo", "roubo_em_coletivo"),
    ("SEG-011", "Roubos a estabelecimentos comerciais", "roubos-estabelecimentos-comerciais", "roubo_comercio"),
    ("SEG-012", "Roubos a residências", "roubos-residencias", "roubo_residencia"),
    ("SEG-013", "Roubos de cargas", "roubos-cargas", "roubo_carga"),
    ("SEG-014", "Furtos de veículos", "furtos-veiculos", "furto_veiculos"),
    ("SEG-015", "Furtos de celulares", "furtos-celulares", "furto_celular"),
    ("SEG-016", "Ameaças", "ameacas", "ameaca"),
    ("SEG-017", "Estelionatos", "estelionatos", "estelionato"),
    ("SEG-018", "Letalidade violenta", "letalidade-violenta", "letalidade_violenta"),
    ("SEG-019", "Roubos de rua", "roubos-rua", "roubo_rua"),
    ("SEG-020", "Total de roubos", "total-roubos", "total_roubos"),
    ("SEG-021", "Total de furtos", "total-furtos", "total_furtos"),
    ("SEG-022", "Pessoas desaparecidas", "pessoas-desaparecidas", "pessoas_desaparecidas"),
    ("SEG-023", "Recuperação de veículos", "recuperacao-veiculos", "recuperacao_veiculos"),
    ("SEG-024", "Registros de ocorrência", "registros-ocorrencia", "registro_ocorrencias"),
    ("SEG-025", "Tráfico de drogas", "trafico-drogas", "trafico_drogas"),
    ("SEG-026", "Extorsões", "extorsoes", "extorsao"),
    ("SEG-027", "Lesões corporais seguidas de morte", "lesoes-corporais-seguidas-morte", "lesao_corp_morte"),
    ("SEG-028", "Encontros de cadáver", "encontros-cadaver", "encontro_cadaver"),
    ("SEG-029", "Encontros de ossada", "encontros-ossada", "encontro_ossada"),
    ("SEG-030", "Homicídios culposos no trânsito", "homicidios-culposos-transito", "hom_culposo"),
    ("SEG-031", "Lesões corporais culposas no trânsito", "lesoes-corporais-culposas-transito", "lesao_corp_culposa"),
    ("SEG-032", "Policiais militares mortos em serviço", "policiais-militares-mortos-servico", "pol_militares_mortos_serv"),
    ("SEG-033", "Policiais civis mortos em serviço", "policiais-civis-mortos-servico", "pol_civis_mortos_serv"),
    ("SEG-034", "Roubos a bancos", "roubos-bancos", "roubo_banco"),
    ("SEG-035", "Roubos de caixas eletrônicos", "roubos-caixas-eletronicos", "roubo_cx_eletronico"),
    ("SEG-036", "Roubos com condução para saque", "roubos-conducao-saque", "roubo_conducao_saque"),
    ("SEG-037", "Roubos após saque", "roubos-apos-saque", "roubo_apos_saque"),
    ("SEG-038", "Roubos de bicicletas", "roubos-bicicletas", "roubo_bicicleta"),
    ("SEG-039", "Outros roubos", "outros-roubos", "outros_roubos"),
    ("SEG-040", "Furtos a transeuntes", "furtos-transeuntes", "furto_transeunte"),
    ("SEG-041", "Furtos em transporte coletivo", "furtos-transporte-coletivo", "furto_coletivo"),
    ("SEG-042", "Furtos de bicicletas", "furtos-bicicletas", "furto_bicicleta"),
    ("SEG-043", "Outros furtos", "outros-furtos", "outros_furtos"),
    ("SEG-044", "Extorsões mediante sequestro", "extorsoes-mediante-sequestro", "sequestro"),
    ("SEG-045", "Extorsões com privação momentânea da liberdade", "extorsoes-privacao-momentanea-liberdade", "sequestro_relampago"),
    ("SEG-046", "Apreensões de drogas", "apreensoes-drogas", "apreensao_drogas"),
    ("SEG-047", "Apreensões de drogas por posse", "apreensoes-drogas-posse", "posse_drogas"),
    ("SEG-048", "Apreensões de drogas sem autor", "apreensoes-drogas-sem-autor", "apreensao_drogas_sem_autor"),
    ("SEG-049", "Autos de prisão em flagrante", "autos-prisao-flagrante", "apf"),
    ("SEG-050", "Autos de apreensão de adolescentes", "autos-apreensao-adolescentes", "aaapai"),
    ("SEG-051", "Cumprimentos de mandados de prisão", "cumprimentos-mandados-prisao", "cmp"),
]
# A unidade publicada obedece à metodologia de agregação por título do ISP-RJ.
# O campo interno `registros` do JSON/CSV é apenas uma chave numérica uniforme:
# sua unidade deve ser interpretada por `unidade` e não presumida como casos.
VICTIM_FIELDS = frozenset({
    "hom_doloso", "latrocinio", "hom_por_interv_policial", "tentat_hom",
    "lesao_corp_dolosa", "estupro", "ameaca", "letalidade_violenta",
    "pessoas_desaparecidas", "lesao_corp_morte", "encontro_cadaver",
    "encontro_ossada", "hom_culposo", "lesao_corp_culposa",
    "pol_militares_mortos_serv", "pol_civis_mortos_serv",
})
# O ISP possui base específica de roubos e furtos de bicicleta desde 07/2015.
# Não interpretar meses anteriores como zero, ainda que a base agregada tenha campos vazios/zero.
SERIES_START = {"roubo_bicicleta": "2015-07", "furto_bicicleta": "2015-07"}
AGGREGATE_FIELDS = frozenset({
    "letalidade_violenta", "roubo_rua", "total_roubos", "total_furtos",
})
METODOLOGIA_ISP = "https://www.ispdados.rj.gov.br/MetodologiaAgregacao.html"


def unit_of(field):
    if field == "registro_ocorrencias":
        return "registros"
    return "vítimas" if field in VICTIM_FIELDS else "casos"


MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def normalized(value):
    value = unicodedata.normalize("NFD", str(value).strip().lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def decode(data):
    for charset in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(charset)
            if "munic" in normalized(text[:2000]) or "fmun_cod" in text[:2000]:
                return text, charset
        except UnicodeDecodeError:
            continue
    raise ValueError("O arquivo do ISP não contém cabeçalho municipal reconhecido")


def read_official(path=None):
    if path:
        content = Path(path).read_bytes()
    else:
        content = download(URL, 40_000_000)
    if not 50_000 < len(content) <= 40_000_000:
        raise ValueError("Tamanho inesperado da base municipal ISP")
    text, charset = decode(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    cols = set(reader.fieldnames or [])
    required = {"ano", "mes"} | {spec[3] for spec in SPEC}
    if not required <= cols:
        raise ValueError(f"Esquema do ISP diferente do esperado; faltam {sorted(required-cols)}")
    if not ({"municipio", "fmun_cod", "cod_municipio", "id_municipio"} & cols):
        raise ValueError("Sem identificador municipal na fonte")
    found = {}
    for record in reader:
        code = str(record.get("fmun_cod") or record.get("cod_municipio")
                   or record.get("id_municipio") or "").strip().replace(".0", "")
        municipal_name = normalized(record.get("municipio", ""))
        is_marica = code in ("330270", "3302700") or municipal_name == "marica"
        if not is_marica:
            continue
        if code and code not in ("330270", "3302700"):
            raise ValueError(f"Nome de Maricá com código inesperado: {code}")
        if municipal_name and municipal_name != "marica":
            raise ValueError(f"Código de Maricá com nome inesperado: {municipal_name}")
        year, month = int(record["ano"]), int(record["mes"])
        if not 2014 <= year <= datetime.now(timezone.utc).year or not 1 <= month <= 12:
            raise ValueError("Competência fora do período válido")
        date = f"{year}-{month:02d}"
        if date in found:
            raise ValueError(f"Competência duplicada para Maricá: {date}")
        fields = {}
        for _, _, _, field in SPEC:
            raw = str(record.get(field, "")).strip()
            if raw in ("", "-", "NA", "...", ".."):
                fields[field] = None
            elif re.fullmatch(r"[0-9]+", raw):
                fields[field] = int(raw)
            else:
                raise ValueError(f"Valor não inteiro/inesperado em {field} {date}: {raw!r}")
        found[date] = fields
    rows = [{"competencia": dt, **found[dt]} for dt in sorted(found)]
    if len(rows) < 120 or rows[0]["competencia"] != "2014-01":
        raise ValueError(f"Cobertura municipal insuficiente: {len(rows)} registros, início {rows[0]['competencia'] if rows else 'sem dados'}")
    dates = [r["competencia"] for r in rows]
    expected = []
    year, month = 2014, 1
    while f"{year}-{month:02d}" <= dates[-1]:
        expected.append(f"{year}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    if dates != expected:
        raise ValueError("Há competências ausentes/duplicadas no conjunto base do ISP; verificar antes de publicar")
    if any(sum(r[field] is not None for r in rows) < 120 for _, _, _, field in SPEC):
        raise ValueError("Série insuficiente para algum indicador, sem inventar dados")
    return rows, hashlib.sha256(content).hexdigest(), charset


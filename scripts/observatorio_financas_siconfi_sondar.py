#!/usr/bin/env python3
"""Sondagem read-only de contas anuais de Maricá na API Siconfi.

Nunca publica resultado automaticamente. Recupera contas, estágios e fontes para
conferência editorial antes de gerar séries municipais.
"""
import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

BASE = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/dca"
ENTE = 3302700
DELAY = 1.10


def get_dca(ano, anexo):
    params = urlencode({
        "an_exercicio": ano, "id_ente": ENTE, "no_anexo": anexo,
        "limit": 5000, "offset": 0,
    })
    items = []
    url = BASE + "?" + params
    pages = 0
    while url:
        pages += 1
        if pages > 8:
            raise ValueError("Paginação inesperada: mais de 8 páginas")
        if urlparse(url).hostname != "apidatalake.tesouro.gov.br":
            raise ValueError("Próxima página aponta para host não oficial")
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "MaricaWiki-Indicadores/1.0"})
        with urlopen(request, timeout=35) as response:
            data = json.load(response)
        if not isinstance(data, dict) or "items" not in data:
            raise ValueError("Resposta não tem campo items")
        items.extend(data["items"])
        if data.get("hasMore"):
            next_page = next((link.get("href") for link in data.get("links", []) if link.get("rel") == "next"), None)
            if not next_page:
                raise ValueError("hasMore sem URL de próxima página")
            url = next_page
            time.sleep(DELAY)
        else:
            url = None
    return items


def resumir(ano, anexo, records):
    # Apenas contas consolidadas candidatas e seus estágios; não somar rubricas.
    matches = []
    for row in records:
        conta = str(row.get("conta", ""))
        cod = str(row.get("cod_conta", ""))
        coluna = str(row.get("coluna", ""))
        upper = conta.upper()
        if "TOTAL DAS RECEITAS" in upper or "TOTAL GERAL DA DESPESA" in upper or "TOTAL DESPESAS" in upper:
            matches.append({
                "conta": conta, "cod_conta": cod,
                "coluna": coluna, "valor": row.get("valor"),
                "rotulo": row.get("rotulo"),
                "instituicao": row.get("instituicao"),
            })
    # Rubricas detalhadas para novos indicadores de despesa (6.2.3 a 6.2.6).
    # Não somar subcontas: identificar o único agregado oficial por ano/estágio.
    detalhadas = []
    if anexo == "DCA-Anexo I-D":
        for row in records:
            account = str(row.get("conta", "")).upper()
            if "PESSOAL E ENCARGOS SOCIAIS" in account or "INVESTIMENTOS" in account:
                if str(row.get("coluna", "")) != "Despesas Liquidadas":
                    continue
                detalhadas.append({
                    "cod_conta": row.get("cod_conta"),
                    "conta": row.get("conta"),
                    "coluna": row.get("coluna"),
                    "valor": row.get("valor"),
                    "rotulo": row.get("rotulo"),
                })
    # Tenta registrar pistas quando a nomenclatura da conta consolidada mudar.
    sample = []
    if not matches:
        candidates = [r for r in records if "TOTAL" in str(r.get("conta", "")).upper()]
        sample = [
            {"conta": r.get("conta"), "coluna": r.get("coluna"), "valor": r.get("valor"), "rotulo": r.get("rotulo")}
            for r in candidates[:15]
        ]
    return {
        "ano": ano, "anexo": anexo, "linhas": len(records),
        "colunas_disponiveis": sorted(set(str(r.get("coluna", "")) for r in records))[:30],
        "contas_consolidadas_candidatas": matches[:25],
        "amostra_se_nao_encontradas": sample,
        "rubricas_detalhadas": detalhadas[:35],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anos", type=int, nargs="+", default=[2024, 2025])
    opts = parser.parse_args()
    for year in opts.anos:
        for anexo in ("DCA-Anexo I-C", "DCA-Anexo I-D"):
            try:
                rows = get_dca(year, anexo)
                result = resumir(year, anexo, rows)
                print("SICONFI_RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
            except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
                print("SICONFI_ERROR " + json.dumps({
                    "ano": year, "anexo": anexo,
                    "erro": type(exc).__name__, "detalhe": str(exc)[:280],
                }, ensure_ascii=False), flush=True)
            time.sleep(DELAY)


if __name__ == "__main__":
    main()

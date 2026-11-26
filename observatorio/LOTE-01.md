# Lote 01 — Demografia e bases auxiliares

Versão inicial: 26/11/2026. São 21 arquivos agregados em CSV/JSON; não incluem microdados, documentos pessoais ou credenciais. Preservados os nomes, valores e metadados do portal. O manifesto identifica o blob Git de cada arquivo.

## Ressalvas

- DEM-001: população presente até 1920; residente de 1940 a 2022. O valor de 1890 é compilação histórica de fonte secundária; manter atribuição. Em 2010, 127.461 na série principal, 127.519 como referência alternativa.
- DEM-002: taxa geométrica anual; cálculo confirmado ao arredondamento publicado.
- DEM-003: densidades oficiais, sem recálculo retroativo com área atual.
- DEM-004: 1991/2010 com percentuais arredondados do IDR; 2022 total de 197.277 habitantes, 94.835 homens e 102.442 mulheres.
- DEM-005 e DEM-006: universos domiciliares distintos; respeitar notas dos arquivos. Médias conferidas ao arredondamento.
- POP/FIN-POP: 2023 nulo; Censo 2022 não é estimativa anual. Denominadores comuns coincidem.
- FROTA: posição dezembro, frota registrada, não circulação. CSV e JSON coincidem.

A migração não constitui revalidação das fontes externas nem define licença geral. FIN-POP e FROTA são espelhos iniciais: a transferência de suas rotinas produtoras será tratada com Finanças e Segurança, respectivamente. Não atualizar de forma independente as bases relacionadas.

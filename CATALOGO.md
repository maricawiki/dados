# Catálogo de dados

| Identificador | Arquivo | Fonte | Cobertura | Situação |
|---|---|---|---|---|
| IPCA-IBGE-1737 | [JSON](observatorio/IPCA-IBGE-1737.json) | [IBGE/SIDRA, tabela 1737, variável 2266](https://sidra.ibge.gov.br/tabela/1737) | 2000-01 a 2026-10 | Piloto de migração; conferência interna de estrutura e integridade |

A cobertura registrada corresponde à versão inicial do piloto, não a uma consulta em tempo real. 

## Lote 1 — Demografia e bases auxiliares

| Base | Arquivos | Fonte e cobertura |
|---|---:|---|
| DEM-001 a DEM-006 | 16 | IBGE, IDR, PLHIS e compilação histórica referenciada; 1872–2022 conforme indicador |
| POP-IBGE-MARICA-2014-2025 | 2 | IBGE, 2014–2025; 2023 nulo |
| FIN-POP-IBGE-2019-2025 | 1 | IBGE, 2019–2025; 2023 nulo |
| FROTA-MARICA-ANUAL | 2 | SENATRAN/RENAVAM, dezembro de 2014–2025 |

[Inventário e ressalvas](observatorio/LOTE-01.md) · [Manifesto de integridade](observatorio/lote-01.manifest.json). Cópia fiel das séries existentes, não nova coleta. As rotinas que geram bases fiscais e taxas de segurança permanecem no site até migração conjunta.

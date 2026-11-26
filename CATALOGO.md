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

## Lote 02 — Finanças e Previdência (parcial)

| Base | Arquivos | Fonte e cobertura |
|---|---:|---|
| FIN-001 a FIN-017 | 34 | STN/Siconfi DCA, IBGE para denominadores; 2019–2025 |
| PREV-001 a PREV-004 | 9 | MPS/CADPREV DRAA e suplementos AEPS, 2015–2026 |
| PREV-005 (série agregada) | 2 | MPS/CADPREV DAIR, 2017-01 a 2026-07 |

[Notas de migração](observatorio/LOTE-02.md) · [Manifesto](observatorio/lote-02.manifest.json). Os dez detalhamentos anuais da carteira estão pendentes de revisão de identificadores de contas bancárias. A série agregada PREV-005 permanece um espelho até o corte conjunto. Não houve nova coleta.

## Lote 03 — Economia e Trabalho

| Base | Arquivos | Fonte |
|---|---:|---|
| ECO-001 a ECO-010 | 20 | IBGE/SIDRA, CEMPRE, MTE/RAIS/ONMT e Receita Federal/SINAC/SIMEI |
| TRB (incluindo séries complementares ONMT) | 72 | MTE/Novo Caged, RAIS, IDR e SINE/Observatório do Trabalho/DIEESE |

[Notas e ressalvas](observatorio/LOTE-03.md) · [Manifesto](observatorio/lote-03.manifest.json). Somente agregados estatísticos já existentes no portal; nenhuma transferência de microdados, documentos ou espelhos brutos de terceiros. Não houve nova coleta.

## Lote 04 — Educação e Saúde

| Base | Arquivos | Fonte |
|---|---:|---|
| EDU-001, 002, 004–017 | 32 | INEP/Censo Escolar, IDEB, relatório municipal do PME |
| SAU-001, 002, 004–006 | 11 | Ministério da Saúde/CNES, SES-RJ/SINASC/SIM, IBGE |

[Notas e ressalvas](observatorio/LOTE-04.md) · [Manifesto](observatorio/lote-04.manifest.json). Agregados municipais; sem microdados de alunos, pacientes ou profissionais. Nenhuma nova coleta.

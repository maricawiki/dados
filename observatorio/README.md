# Observatório de Indicadores

## Piloto: IPCA nacional

Arquivo: [IPCA-IBGE-1737.json](IPCA-IBGE-1737.json).

Fonte: IBGE/SIDRA, tabela 1737, variável 2266, Brasil. O arquivo preserva a série mensal de números-índices e as médias anuais dos exercícios completos, com metodologia e URL da fonte nos metadados.

Versão inicial: 322 competências de janeiro de 2000 a outubro de 2026; 26 médias anuais (2000–2025); ano-base automático 2025. Conferência interna de continuidade mensal, unicidade, valores positivos e recomposição das médias anuais. Não foi feita uma nova consulta à fonte oficial nesta migração.

Git blob da versão inicial: `4455b0c7ed75eadc29e0c6e73d60bd11f9c5bcd9`.

A rotina `scripts/observatorio_ipca_atualizar.py` preserva a metodologia original. O workflow valida a base em PRs e, após merge na main, consulta a fonte nos dias 10, 15 e 20, às 09h17 de Maricá (UTC−3), com atualização manual opcional. Somente alterações validadas geram commit. A integração do portal é homologada separadamente; este repositório não possui credenciais de publicação do site.

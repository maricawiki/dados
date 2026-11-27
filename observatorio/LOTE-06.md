# Lote 06 — Segurança Pública

246 arquivos, hashes idênticos ao portal existente. 51 indicadores de registros absolutos (102 arquivos), 46 séries oficiais de taxas (138 arquivos), três taxas anuais derivadas por frota (6 arquivos). Triagem de estruturas e identificadores, sem registros individualizados. As duas dependências FROTA-MARICA-ANUAL já publicadas no lote 01 têm os mesmos hashes. Não houve alteração dos valores publicados.

- Registros absolutos: a variável registros no formato é chave uniforme; a unidade pode ser vítimas, casos ou registros, conforme a fonte.
- Taxas oficiais: bases mensal e anual independentes; não somar nem calcular média simples de taxas mensais. A fonte tem cobertura variável e não equivale às taxas por frota ou efetivo policial.
- SEG-024: a coluna registro_ocorrencias está ausente na fonte mensal consultada em 17/11 e no teste da correção. Preservar a série já validada e sua proveniência, sem imputar valores. A ausência não impede verificar outras variáveis.
- Taxas por veículos: denominador de dezembro da SENATRAN, numeradores ISP dos anos completos e arredondamento original. Não extrapolar. O efetivo policial municipal não está certificado, portanto não publicar taxas por efetivo.
- Os scripts de sondagem são derivados dos leitores auditados do site, sem lógica editorial nem credenciais, e com tentativas limitadas. O workflow público apenas detecta alterações e registra alertas; não grava dados nem publica automaticamente. Geração de novas versões, integração editorial e transferência da rotina SENATRAN ainda requerem corte coordenado.

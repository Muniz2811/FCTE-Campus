# Orientações do módulo RAG

- Este módulo está em `fcte-campus/backend/`. Caminhos abaixo relativos a backend/. Código em `rag/`, agrupado em ingestao, consulta e armazenamento. Contrato HTTP em rag/api.py.
- Requisitos do usuário prevalecem. Não recriar a camada src/unb_gama_rag nem duplicar documentos explicativos.
- Configuração em config/rag.yaml. Fontes em data/catalogo. Banco em data/index/chroma. Logs privados em data/execucoes.
- Preservar originais, hashes, banco e rodadas históricas de avaliação. Limpeza não deve apagar evidências.
- Nunca copiar chaves ao frontend ou Git. Reusar .env externo apenas por argumento explícito.
- Contrato com o PWA: porta 8001, /api/v1/chat e /api/v1/health. Manter compatibilidade.
- RU e disciplinas pertencem ao outro grupo. Não inventar rotas, ocupação ou localização atual.
- Modelos locais E5 e reranker com revisão fixa; Gemini apenas gera a resposta citada.
- Pontuações de reranker/cosseno não são probabilidades de verdade. Avaliar cortes e registrar limitações.
- O usuário prefere verificações existentes e avaliações reais; não criar testes redundantes ou muitos Markdown.
- Usar README.md e RELATORIO_SEMANA_3_LLM_X_RAG.md para explicação/diagrama. Resultados medidos em avaliacao/resultados. Preservar registros históricos da pasta anterior; seus caminhos absolutos refletem a execução original.

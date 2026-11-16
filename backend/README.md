# RAG do FCTE Campus

Backend local de consulta a documentos do campus Gama. O FCTE Campus envia perguntas por HTTP; o RAG recupera evidências, reordena com um cross-encoder multilíngue e pede ao Gemini uma resposta com citações.

O armazenamento pode ser Chroma local (padrão) ou Supabase/pgvector. Consulte o
[tutorial de migração](supabase/README.md) para enviar os vetores existentes sem refazer embeddings.

`RAG_PROFILE=full` mantém o pipeline E5 + BM25/RRF + reranker. O deploy Docker usa
`RAG_PROFILE=light` com Supabase: lê textos, recupera por BM25 e gera via Gemini, sem modelos locais.
As dependências desse perfil estão em `requirements-api.txt`; a documentação de deploy está no README da raiz.

## Iniciar com o aplicativo

Este backend faz parte do repositório [FCTE Campus](../README.md). Na raiz do repositório:

```powershell
npm run rag:prepare
npm run dev:rag
```

O primeiro comando prepara o reranker uma vez e exige internet. E5 e reranker executam na CPU; apenas a geração Gemini usa API. Em ambiente novo, siga o preparo de `backend/.venv`, `backend/.env` e do índice no README da raiz. Os comandos Python abaixo são executados dentro de `backend/`.

Em outro terminal, na raiz do repositório: `npm.cmd run dev`. Abra http://127.0.0.1:5173. A API permanece na porta 8001 e mantém `POST /api/v1/chat` e `GET /api/v1/health`. O proxy do Vite usa `/api/v1`. Nenhuma chave vai ao navegador. O projeto agora contém somente o chat, sem mapa/PWA. O Dockerfile da raiz reúne frontend, modelos e índice num único serviço; veja as instruções de deploy no README da raiz.

## Organização das pastas

| Pasta | Conteúdo e finalidade |
|---|---|
| `rag/` | Código Python executado pela aplicação. Substitui a camada dupla `src/unb_gama_rag`. |
| `rag/ingestao/` | Aquisição HTML/PDF, extração, catálogo, normalização de entidades, contagem de tokens e chunking. |
| `rag/consulta/` | Busca E5 + BM25/RRF, reranker, contexto de conversa, geração Gemini e serviço que coordena o chat. |
| `rag/armazenamento/` | Embeddings E5, cliente Chroma, indexação e manifesto de integridade. |
| `rag/api.py` | Contrato HTTP do chat, validação, tratamento de erros e frontend compilado em produção. |
| `rag/config.py` | Leitura da configuração e resolução de caminhos pela raiz do projeto. |
| `config/` | Parâmetros de ingestão, busca, modelos e entidades do campus. |
| `data/catalogo/` | Fontes, aprovação editorial e registro da expansão. |
| `data/originais/` | HTML/PDF preservados, por fonte e versão; fora do Git. |
| `data/extraido/` | Texto preparado com seção/página e hash do original. |
| `data/chunks/` | Chunks e configuração usada para produzi-los. |
| `data/index/` | Chroma persistido, vetores E5 e manifestos. É o banco local; não apagar para limpar arquivos. |
| `data/execucoes/` | Logs privados das consultas, perguntas, rankings, respostas e parâmetros; fora do Git. |
| `avaliacao/` | Gabarito e resultados reais por rodada. Históricos preservados para rastreabilidade. |
| `scripts/` | Comandos finos para executar cada etapa, servir a API e avaliar. |
| `tests/` | Verificações existentes de integridade, API e pipeline; não chamam Gemini. |
| `RELATORIO_SEMANA_3_LLM_X_RAG.md` | Fluxo, diagrama, integração e comparação real entre a LLM isolada e o RAG atual. |
| `.cache/` | Pesos dos modelos baixados, fora do Git; evita repetir downloads. |
| `.venv/` | Ambiente Python local, fora do Git. |

## O que acontece em uma pergunta

1. Recuperar somente documentos aprovados, elegíveis e com validade compatível.
2. E5 busca significado e BM25 busca palavras/siglas. RRF combina os rankings.
3. O reranker lê os pares pergunta–trecho dos trinta melhores candidatos e os reordena.
4. Aplicar o corte de pontuação configurado e selecionar **até** cinco trechos, no máximo dois por fonte. Não preencher vagas com trechos descartados.
5. Gemini responde usando os trechos. Citações precisam corresponder a IDs realmente recuperados.
6. Registrar a execução com origem, versão da base e parâmetros.

A ordenação final combina por RRF (k=60) as posições híbrida e neural. O corte experimental de logit é -4; notas abaixo dele são descartadas, sem completar artificialmente cinco resultados.

O reranker é `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revisão fixa, local. Sua nota é um logit de relevância, **não uma probabilidade de verdade**. Os documentos são limitados a 512 tokens no par com a pergunta. Alterar reranker/busca não exige refazer os embeddings E5 ou o Chroma. Os resultados de corte e comparação ficam em `avaliacao/resultados/reranker-diagnostico/`.

## Preparar ou conferir a base

Execute pela raiz do repositório, sem precisar configurar PYTHONPATH:

```powershell
.\.venv\Scripts\python.exe scripts/03_validar_catalogo.py
.\.venv\Scripts\python.exe scripts/04_chunks.py
.\.venv\Scripts\python.exe scripts/05_indexar.py
.\.venv\Scripts\python.exe scripts/06_conferir.py
.\.venv\Scripts\python.exe scripts/perguntar.py "Onde fica o laboratório COSMOS?"
.\.venv\Scripts\python.exe -m pytest -q
```

`01_adquirir.py` baixa fontes; `02_extrair.py` prepara o texto. Não é necessário reexecutar ingestão ao iniciar a API. Chunks: alvo 300 tokens, sobreposição até 40 apenas em subdivisões longas. E5: 384 dimensões, prefixos passage/query e normalização L2.

A base possui 42 propostas aprovadas, 37 fontes indexadas e 174 chunks. Cinco exclusões estão documentadas no catálogo: quatro downloads indisponíveis e o mapa CEPLAN histórico de 2015. O edital DOC-042 é histórico e não participa das consultas atuais. RU, disciplinas, ocupação ao vivo e cálculo de trajetos de ônibus estão fora do módulo.

## Evidências e limites

As avaliações anteriores são fotografias das configurações de cada rodada. Seus percentuais não devem ser atribuídos automaticamente ao reranker. O diagnóstico novo compara a seleção dos trechos; aprovação dos IDs de citação não substitui revisão semântica da resposta. Nenhum limiar comprova verdade ou atualidade. Perguntas conhecidas usadas no ajuste não são teste independente.

Referências: [retrieve and rerank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) e [modelo multilíngue](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1).

## Resultado desta alteração

O diagnóstico nas mesmas quinze perguntas preservou evidência em **12/12 respondíveis** e reduziu os trechos enviados de **75 para 58**. Foram relevantes **16/58 (27,59%)**, contra 17/75 (22,67%) na rodada anterior. A precisão melhorou proporcionalmente, mas o número absoluto de evidências relevantes caiu em um trecho; a meta de 40% ainda não foi atingida. Não é avaliação independente porque essas perguntas participaram do ajuste.

Três consultas reais pela API tiveram HTTP 200: empréstimo para visitantes (agora inclui a restrição específica), correção de biblioteca na UAC e ausência de ocupação da I10 (zero trechos). Os **74 testes existentes passaram** e o Chroma reabriu sem ingestão. Registros em `avaliacao/resultados/reranker-diagnostico/`. Histórico de fundamentação 49/49 pertence à rodada anterior, não foi recalculado para todas as respostas com reranker.

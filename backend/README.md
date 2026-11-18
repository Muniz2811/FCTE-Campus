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

Os testes acima não chamam o Gemini. Para validar o fluxo multiagente com o índice local e o Gemini real (cerca de 25 chamadas; o servidor `dev:rag` deve estar parado, porque dois processos não podem abrir o mesmo Chroma no Windows):

```powershell
$env:RAG_TEST_GEMINI='1'; $env:HF_HUB_OFFLINE='1'
.\.venv\Scripts\python.exe -m pytest tests/test_multiagente_gemini.py -v -s
```

Para comparar os três modos, use `scripts/comparar_tres_modos.py --conjunto conferencia` (perguntas formais) ou `--conjunto coloquial` (conjunto de estresse que favorece o multiagente; relate sempre junto da conferência). Detalhes em `RELATORIO_MULTIAGENTE.md`.

`01_adquirir.py` baixa fontes; `02_extrair.py` prepara o texto. Não é necessário reexecutar ingestão ao iniciar a API. Chunks: alvo 300 tokens, sobreposição até 40 apenas em subdivisões longas. E5: 384 dimensões, prefixos passage/query e normalização L2.

A base possui 46 fontes aprovadas, 41 fontes indexadas e 214 chunks. As quatro fichas de mapeamento acrescentam 40 chunks aos 174 anteriores. Cinco exclusões estão documentadas no catálogo: quatro downloads indisponíveis e o mapa CEPLAN histórico de 2015. O edital DOC-042 é histórico e não participa das consultas atuais. RU, disciplinas, ocupação ao vivo e cálculo de trajetos de ônibus estão fora do módulo.

## Alimentar o RAG com os mapas da coleta

`scripts/importar_mapas.py` importa os ambientes nomeados da UAC e da UED. Não modifica os mapas nem importa objetos puramente visuais (paredes, telhados, jardins, degraus e salas sem nome). A edição no SQLite local da coleta prevalece sobre o GeoJSON inicial. Edições feitas somente no servidor precisam ser exportadas antes; não há sincronização automática com o Render.

O snapshot está em `data/imports/mapas/`: uma fonte por prédio/andar, com 177 ambientes e 14 banheiros. Cada ficha preserva IDs, nomes, andar, pontos aproximados, hash do mapa e commit da coleta. A aprovação refere-se ao uso do inventário existente autorizado por Pedro; não afirma uma nova vistoria em campo. Banheiro, sanitário e WC aparecem no texto para busca lexical. Referências próximas são calculadas entre pontos no mesmo piso, até 25 m no desenho; não são distâncias de caminhada nem rotas acessíveis confirmadas. Plantas com posições explicitamente inferidas, como a do LDTEA, não entram nessa importação.

Para atualizar, na **raiz do FCTE-Campus**, com o repositório da coleta ao lado:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/importar_mapas.py --coleta ../coleta-fcte
.\backend\.venv\Scripts\python.exe backend/scripts/04_chunks.py
$env:RAG_PROFILE='full'
$env:RAG_INDEX_BACKEND='chroma'
npm.cmd run rag:index
npm.cmd run rag:migrate -- --preparar
Remove-Item Env:RAG_PROFILE, Env:RAG_INDEX_BACKEND
```

No Mac, use `./backend/.venv/bin/python`, `npm` e `RAG_PROFILE=full RAG_INDEX_BACKEND=chroma npm run rag:index` em lugar das variáveis PowerShell. A importação gera fichas e texto extraído; o chunking e o E5 são os mesmos do pipeline existente. O deploy BM25 continua sem baixar esses modelos.

`--preparar` envia uma nova coleção completa sem trocar a coleção ativa usada pelo deploy antigo. A API nova escolhe o snapshot pelos hashes do catálogo e dos chunks do seu próprio código. O manifesto só é disponibilizado após a conferência dos IDs/contagem. Depois de commit/push dos arquivos versionados, faça deploy no Render: o health deve mostrar 41 fontes e 214 chunks. Não é necessário alterar o contrato `/perguntar`, o cliente do Milton ou executar SQL novo. O modo antigo `--enviar` continua disponível, mas troca a coleção ativa e deve ser usado com cuidado durante atualizações de corpus.

Exemplos: “Onde tem banheiro no térreo da UAC?”, “Onde ficam os sanitários do piso superior da UED?”, “Em qual andar fica a I10?” e “Onde fica a S10?”. A pergunta por um banheiro mais próximo de você continua exigindo uma posição de origem e cálculo geográfico separado. As métricas anteriores permanecem históricas; esta expansão não reavalia automaticamente aqueles resultados.

## Navegação do Milton usando o inventário do RAG

O contrato `POST /perguntar` aceita um campo opcional `contexto.navegacao`. As operações `listar`, `contar`, `proximidade` e `rota` consultam exatamente as fichas em `data/imports/mapas`, conferidas contra o hash do catálogo. Os filtros opcionais são `categoria`, `predio_id`, `andar`, `nome` e `acessivel`. Essa consulta estruturada não chama Gemini, E5 ou reranker, nem se limita ao top-5 de chunks. Perguntas documentais continuam no pipeline existente.

O resultado inclui `navegacao.locais`, com `predio_id`, `ambiente_id`, nome, andar, categoria e `fonte_n`, além das referências das fichas. A unidade de citação `map_<fonte>_<hash>` representa o inventário JSON completo; não é um chunk vetorial. O inventário inicial cobre UAC/UED (14 banheiros), não garante cobertura de todos os ambientes do campus.

O coleta-fcte valida o contrato e os IDs contra suas plantas. No navegador, o motor A* existente compara rotas caminháveis; nenhuma posição pessoal é enviada ao RAG, Gemini, Supabase ou histórico do chat. GPS negado, impreciso, antigo ou fora do campus abre escolha manual de origem. Se o GPS estiver dentro de um prédio, o Milton pede um ambiente/andar, pois GPS não identifica pavimento. Nomes ambíguos pedem escolha de destino. Rotas incompletas não sustentam uma afirmação de menor percurso global.

Para publicar: primeiro atualize o FCTE-Campus (o Dockerfile passa a incluir as fichas JSON) e depois o coleta-fcte. Os mesmos `G09_API_URL`, `G09_API_TOKEN` e `RAG_API_TOKEN` continuam válidos. Não há novo SQL, migração de banco ou reindexação de embeddings para essa integração. Perguntas normais e o contrato do RUmo permanecem compatíveis.

## Evidências e limites

As avaliações anteriores são fotografias das configurações de cada rodada. Seus percentuais não devem ser atribuídos automaticamente ao reranker. O diagnóstico novo compara a seleção dos trechos; aprovação dos IDs de citação não substitui revisão semântica da resposta. Nenhum limiar comprova verdade ou atualidade. Perguntas conhecidas usadas no ajuste não são teste independente.

Referências: [retrieve and rerank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) e [modelo multilíngue](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1).

## Resultado desta alteração

O diagnóstico nas mesmas quinze perguntas preservou evidência em **12/12 respondíveis** e reduziu os trechos enviados de **75 para 58**. Foram relevantes **16/58 (27,59%)**, contra 17/75 (22,67%) na rodada anterior. A precisão melhorou proporcionalmente, mas o número absoluto de evidências relevantes caiu em um trecho; a meta de 40% ainda não foi atingida. Não é avaliação independente porque essas perguntas participaram do ajuste.

Três consultas reais pela API tiveram HTTP 200: empréstimo para visitantes (agora inclui a restrição específica), correção de biblioteca na UAC e ausência de ocupação da I10 (zero trechos). Os **74 testes existentes passaram** e o Chroma reabriu sem ingestão. Registros em `avaliacao/resultados/reranker-diagnostico/`. Histórico de fundamentação 49/49 pertence à rodada anterior, não foi recalculado para todas as respostas com reranker.

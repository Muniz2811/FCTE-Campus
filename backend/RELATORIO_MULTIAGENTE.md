# FCTE-Campus — Avaliação do RAG Multiagente

**Grupo:** 09 — Residência em IA, FCTE/UnB
**Projeto:** [Muniz2811/FCTE-Campus](https://github.com/Muniz2811/FCTE-Campus)
**Issues:** [#1](https://github.com/Muniz2811/FCTE-Campus/issues/1), [#2](https://github.com/Muniz2811/FCTE-Campus/issues/2), [#3](https://github.com/Muniz2811/FCTE-Campus/issues/3), [#4](https://github.com/Muniz2811/FCTE-Campus/issues/4)
**Situação:** implementação testada com índice local e Gemini real (seção 7.1); rodadas dos três modos executadas com perguntas formais (seção 7.2) e com um conjunto coloquial que favorece o multiagente (seção 7.3); **revisão humana dos julgamentos pendente**; conclusão preliminar na seção 9.

## 1. Objetivo

Comparar (A) Gemini isolado, (B) RAG atual e (C) RAG multiagente com a mesma versão do corpus, modelo Gemini e parâmetros de geração. Medir qualidade factual, recuperação, rastreabilidade, disponibilidade, consumo e custo adicional das correções.

## 2. Arquitetura

```mermaid
flowchart TD
    U([Pergunta]) --> VAGA{Vaga livre?}
    VAGA -- não --> E429[429 consulta em andamento]
    VAGA -- sim --> CTX[Contexto via previousRequestId]
    subgraph PESQ [Pesquisador]
        CTX --> PLAN[Gemini planeja 1–3 subconsultas]
        PLAN --> B[Busca híbrida E5 + BM25/RRF → Chroma → reranker]
        B --> M[Mescla intercalada: até 5 chunks, máx 2 por fonte]
    end
    M --> TEM{Há trechos?}
    TEM -- não --> X1[Abstenção sem chamar o Redator]
    TEM -- sim --> D[Redator Gemini: claims com chunk_ids]
    D --> VAL{chunk_ids citados foram recuperados?}
    VAL -- não --> F502[Falha técnica: citação bloqueada]
    VAL -- sim --> V[Revisor Gemini]
    V -->|aprovar| F([Resposta com fontes])
    V -->|corrigir, 1ª vez| D2[Redator refaz com feedback e claims_problematicas]
    D2 --> V2[Revisor reavalia]
    V2 -->|aprovar| F
    V2 -->|corrigir de novo| X2[Abstenção: nao_aprovado_apos_correcao]
    V -->|insuficiente| X3[Abstenção]
    V2 -->|insuficiente| X3
    F & X1 & X2 & X3 & F502 --> LOG[(Log por requestId) → libera a vaga]
```

A classe `OrquestradorMultiagente` tem orçamento padrão de até 3 buscas, 5 chamadas Gemini e 240 segundos totais. O Pesquisador planeja subconsultas; o Redator produz claims com `chunk_ids`; o backend rejeita referências inexistentes no contexto; o Revisor avalia completude e suporte semântico com decisão `aprovar`, `corrigir` ou `insuficiente`. A correção pode ocorrer **no máximo uma vez**; se o Revisor recusar de novo, a decisão final é `nao_aprovado_apos_correcao`. Quando o próprio Redator se abstém, sua mensagem de lacuna é preservada. O feedback do Revisor é marcado no prompt do Redator como indicação do que revisar, nunca como evidência. Todos os estados, decisões e tempos são registrados por `requestId` em `backend/data/execucoes/multiagent-*.json`; uma falha ao gravar esse log não descarta a resposta (`auditLogSaved: false`) e a vaga de concorrência é sempre liberada.

`/api/v1/multiagent` exige token Bearer em deploy (como `/perguntar`). A comparação ao vivo `/api/v1/comparison/{arm}` permanece pública por decisão do projeto.

A verificação de ID documenta a **cadeia de fonte**, mas não prova automaticamente a verdade semântica. O julgamento humano permanece obrigatório.

Na revisão de integração, o prazo passou a ser conferido antes e depois de cada etapa, inclusive após o parecer final. A execução não publica uma aprovação concluída fora do orçamento. Esse controle é cooperativo: não interrompe à força uma busca local já em andamento. A comparação também preserva a resposta se seu próprio log falhar, sinalizando `auditLogSaved: false`.

Para servir no MacBook, consulte [o tutorial do ngrok](../docs/servir-no-mac.md). O modo somente API mantém `/perguntar` e `/api/v1/multiagent` autenticados, com o chat público independente desativado nessa execução.

## 3. Controle experimental

- **Desenvolvimento/regressão:** `backend/avaliacao/gabarito.json`, 15 perguntas já usadas em ajustes. Esse conjunto **não é cego**.
- **Conferência final:** `backend/avaliacao/conferencia_final.json`, 8 perguntas de formulação nova (2 compostas, 2 de ambiguidade/contexto, 2 de premissas incorretas e 2 sem resposta). As entidades são conhecidas do corpus: portanto não constitui teste de generalização fora do domínio.
- **Paridade:** preservar a mesma `baseVersion`, Gemini configurado, temperatura, limites, data de validade documental e ambiente. O Gemini isolado não recebe documentos; os dois RAGs utilizam a mesma fonte de busca. Registrar hash do corpus, prompts e commit.
- **Ordem:** sorteio determinístico das tarefas para reduzir viés de ordem; execução sequencial para não competir pelo bloqueio de concorrência da API. Registrar tempos de serviço e tentativas.
- **Retentativa:** apenas erros técnicos elegíveis (`429, 500, 502, 503, 504`). Nunca repetir resposta semanticamente ruim para escolher uma mais favorável. Preservar todas as tentativas.
- **Histórico:** o script de comparação executa questões independentes, sem histórico interquestões. Conversas com `previousRequestId` devem ser testadas separadamente com histórico explicitamente registrado, inclusive na comparação Gemini isolado, evitando alegar igualdade quando não houver contexto equivalente.

## 4. Execução

Primeiro, instalar dependências e verificar o índice conforme o README. Em PowerShell na raiz:

```powershell
npm.cmd ci
npm.cmd run rag:check
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_multiagente.py -q
npm.cmd run build
```

Em seguida, com `backend/.env` preenchido localmente e sem registrar credenciais no repositório:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/comparar_tres_modos.py --env-file backend/.env --conjunto desenvolvimento
.\backend\.venv\Scripts\python.exe backend/scripts/comparar_tres_modos.py --env-file backend/.env --conjunto conferencia
```

O script imprime a pasta correspondente à rodada, que conterá `execucoes.json` e `gabarito.json`. Não executar a conferência final até que prompts e código estejam congelados.

Gerar a ficha de julgamentos com o caminho **real** da pasta criada:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/resumir_tres_modos.py backend/avaliacao/resultados/PASTA_DA_RODADA --preparar
```

Preencher todos os campos aplicáveis em `julgamentos.json`, com revisor, observação e fontes originais consultadas. Comparar cada afirmação atômica com seu chunk citado e o original. Então executar:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/resumir_tres_modos.py backend/avaliacao/resultados/PASTA_DA_RODADA
```

O resultado `metricas.json` apresenta numeradores e denominadores. Dados sem revisão continuam N/A, não zero.

## 5. Métricas e denominadores

| Indicador | Numerador | Denominador |
|---|---|---|
| Completude | Perguntas respondíveis integralmente atendidas | Perguntas respondíveis com revisão identificada |
| Corroboração | Afirmações factuais corroboradas | Afirmações factuais julgadas |
| Correção de premissas | Perguntas com premissa explicitamente corrigida | Perguntas com premissa falsa julgadas |
| Reconhecimento de ausência | Abstenções corretas | Perguntas sem resposta julgadas |
| Hit@5 | Respondíveis com pelo menos um trecho relevante entre os cinco | Respondíveis com busca revisada |
| Precisão dos trechos | Todos os trechos relevantes recuperados | Todos os trechos recuperados nos casos julgados, **incluindo perguntas sem resposta** |
| MRR@5 | Soma do inverso do rank do primeiro trecho relevante | Respondíveis com busca revisada |
| Fundamentação | Fatos sustentados pelos chunks citados | Fatos julgados nas respostas com RAG |
| Rastreabilidade | Vínculos claim-chunk resolvidos até o original | Vínculos claim-chunk verificados |
| Adequação das citações | Vínculos cujo chunk realmente sustenta a claim | Vínculos claim-chunk julgados |
| Disponibilidade | Chamadas HTTP 200 | Todas as tentativas, inclusive falhas técnicas |
| Sucesso inicial | Perguntas HTTP 200 na primeira tentativa | Perguntas iniciadas |

A latência válida considera somente respostas HTTP 200; o esforço operacional soma **todas** as tentativas observadas. O consumo por agente é registrado a partir de `usageMetadata`, quando disponível, e não deve ser presumido se ausente.

No multiagente, computar separadamente as revisões `melhorou`, `piorou`, `neutra` e `sem_correcao` após comparar o primeiro rascunho com a versão final, usando as mesmas fontes.

## 6. Baseline já existente (12/11/2026)

A rodada anterior [`semana3-llm-rag-20261112-v1`](https://github.com/Muniz2811/FCTE-Campus/tree/main/backend/avaliacao/resultados/semana3-llm-rag-20261112-v1) comparou **somente Gemini isolado e RAG atual**:

| Medida | Gemini isolado | RAG atual |
|---|---:|---:|
| Completude | 4/12 | 12/12 |
| Correção de premissas | 1/2 | 2/2 |
| Ausência reconhecida | 3/3 | 3/3 |
| Latência média válida | 6,93 s | 11,40 s |
| Sucesso na primeira tentativa | 12/15 | 9/15 |
| Precisão de trechos | N/A | 16/58 |

Esses resultados **não medem** o multiagente e **não são comparáveis diretamente** com uma nova rodada cuja base ou configuração tenha sido alterada.

## 7. Resultados

### 7.1 Testes de integração com Gemini real (issues #1 e #2)

`backend/tests/test_multiagente_gemini.py` usa o índice local e o Gemini configurado (`gemini-3.5-flash-lite`). É pulado sem `RAG_TEST_GEMINI=1`, para a suíte comum não gastar cota. Evidências completas (plano, buscas, rascunhos, pareceres, tokens por agente) em [`avaliacao/resultados/multiagente-gemini-*`](avaliacao/resultados/).

| Cenário | Resultado observado | Chamadas | Tokens |
|---|---|---:|---:|
| Esquemas `Plano`, `SaidaGerador`, `Parecer` | Aceitos pelo Gemini com saída estruturada | 3 | 865 |
| Composta (H01) | 2 subconsultas; COSMOS sala 304 e LEMA sala 103; aprovado | 3 | 4.322 |
| Premissa incorreta (H05) | "A premissa está incorreta… sala 304"; aprovado | 3 | 3.866 |
| Sem resposta (H07) | Abstenção, nenhuma claim | 3 | 3.758 |
| Revisor com erro injetado | Primeiro rascunho substituído por "sala 101, térreo da UAC"; o Revisor real pediu correção citando a sala 304; o Redator corrigiu e o Revisor aprovou | 5 | 6.244 |
| Complemento de conversa | "E lá posso estudar em grupo?" com `previousRequestId`: "lá" resolvido como a biblioteca; cabines individuais e mesas em grupo | 3 + 3 | 9.183 |

O caso do Revisor usa um primeiro rascunho injetado porque, com respostas corretas de primeira, a correção nunca seria acionada; Revisor e correção continuam sendo chamadas reais, e a injeção está registrada na evidência.

### 7.2 Rodada de conferência dos três modos

Pasta: [`avaliacao/resultados/tres-modos-conferencia-20261118T131530Z`](avaliacao/resultados/tres-modos-conferencia-20261118T131530Z). 24/24 execuções concluídas, hashes de código, base e configuração preservados.

**Medidas operacionais** (não dependem de julgamento):

| Medida | Gemini isolado | RAG atual | RAG multiagente |
|---|---:|---:|---:|
| Latência média válida | 11,40 s | 10,25 s | 21,94 s |
| Latência mediana válida | 10,66 s | 9,32 s | 16,34 s |
| Tokens das 8 respostas válidas | 2.502 | 18.743 | 34.054 |
| Chamadas Gemini (multiagente) | — | — | 24 |
| Rodadas de correção | — | — | 0 |
| Sucesso na primeira tentativa | 5/8 | 6/8 | 6/8 |
| Sucesso por tentativa | 8/12 | 8/10 | 8/11 |

As 9 falhas técnicas foram do provedor (8× HTTP 503 de conexão ou alta demanda, 1× 504 por timeout) e atingiram os três modos. No RAG atual, H07 não chamou o Gemini por falta de evidência, por isso o consumo registrado cobre 7/8 respostas.

**Medidas de qualidade: PENDENTES DE REVISÃO HUMANA.** Há uma pré-avaliação não revisada no `julgamentos.json` da pasta local, não versionada. Os números finais entram aqui após a validação com os documentos originais e o recálculo de `metricas.json`.

### Análise das correções

Nenhuma rodada de correção ocorreu nas 8 perguntas da conferência: o Revisor aprovou o primeiro rascunho em todas as respondíveis. O único caso de correção observado com Gemini real é o do rascunho injetado (seção 7.1), em que o resultado melhorou (sala 101 → 304).

### 7.3 Conjunto coloquial — FAVORECE O MULTIAGENTE

> Conjunto de estresse escolhido **depois** de verificar, só com a busca local, que a consulta única do RAG atual não recupera o documento que responde (C01–C06) ou recupera só uma parte (C07). C08 é controle. Testa a hipótese "o multiagente ajuda quando o vocabulário da pessoa difere do dos documentos". **Não estima desempenho médio** e deve ser lido junto da seção 7.2. Definição em [`avaliacao/conferencia_coloquial.json`](avaliacao/conferencia_coloquial.json).

Pasta: [`avaliacao/resultados/tres-modos-coloquial-20261118T150540Z`](avaliacao/resultados/tres-modos-coloquial-20261118T150540Z). 23/24 execuções válidas (C04 do Gemini isolado falhou 3 vezes por 503), hashes preservados. C07 e C08 do multiagente só concluíram na 4ª tentativa, após três HTTP 503 do provedor; todas as tentativas estão registradas.

| Pergunta | Gemini isolado | RAG atual | Multiagente |
|---|---|---|---|
| C01 quadra de futebol | Inventou que não há quadra | Não encontrou | Não encontrou nesta rodada |
| C02 passar mal | Conselho genérico sem fonte | Não encontrou | **Navs da DASU na FCTE** |
| C03 ansiedade | Inventou serviços (CAE, NAP) | Não encontrou | **SOU e DASU** |
| C04 ônibus | Falha do provedor | Não encontrou | Não encontrou |
| C05 cadeira inadequada | Conselho genérico sem fonte | Não encontrou | Não encontrou |
| C06 quantos livros | Absteve-se | Não encontrou | Recuperou DOC-032 e ainda assim se absteve |
| C07 biblioteca + CAPES | Localização vaga | **Errou**: deu a Biblioteca Central (Darcy Ribeiro) | CAPES correto; localização vaga ("na FCTE") |
| C08 wifi (controle) | Aproximado, sem fonte | Correto | Correto |

| Medida operacional | Gemini isolado | RAG atual | Multiagente |
|---|---:|---:|---:|
| Latência mediana válida | 8,5 s | 9,4 s | 30,9 s |
| Tokens das respostas válidas | 2.579 | 10.503 | 36.931 |
| Sucesso na primeira tentativa | 3/8 | 5/8 | 4/8 |
| Rodadas de correção | — | — | 0 |

Leitura preliminar, **pendente de revisão humana**: o multiagente foi melhor em C02, C03 e C07, empatou nas demais e não piorou o controle. O ganho vem da **reformulação das subconsultas pelo Pesquisador**, não do Revisor (nenhuma correção ocorreu). Ele é **instável**: C01 foi respondida corretamente numa sessão da comparação ao vivo (subconsulta "infraestrutura esportiva quadra" encontrou DOC-009) e não foi respondida nesta rodada, com subconsultas diferentes. Em C06 a busca encontrou o documento certo, mas Redator e Revisor não usaram a linha "Quantidade máxima de exemplares: 5".

## 8. Limitações

- 15 perguntas de regressão conhecidas e 8 de conferência com sobreposição de temas; amostra pequena.
- Verificação semântica exige humano; o revisor automático pode aprovar uma afirmação incorreta.
- Chamadas Gemini podem sofrer cota, timeout e variações do provedor.
- Tokens ausentes não podem ser inferidos como zero consumo.
- Testes de carga, usuário real, histórico interturnos e deploy público não são cobertos pelo experimento padronizado.
- O uso de vários agentes consome mais chamadas; benefício precisa superar os custos e o tempo adicional.
- O provedor Gemini respondeu com HTTP 503 ("high demand") e latências de até ~50 s durante os testes. Com 3 a 5 chamadas encadeadas, o multiagente é o modo mais exposto a essas falhas.
- O Revisor detectou uma afirmação **errada** (caso injetado), mas aprovou respostas **incompletas**: a biblioteca localizada só como "na FCTE" e a H06 sem a restrição de empréstimo presente no trecho recuperado.
- O modelo produziu ao menos um escape de caractere quebrado na saída (`Pr#00e9dio`).
- `/api/v1/comparison/multiagente` é público e consome a mesma cota do endpoint protegido.
- Cancelar a requisição no navegador não interrompe a execução no backend, e a busca não tem timeout próprio.

## 9. Conclusão

**PRELIMINAR — pendente de revisão humana dos julgamentos.**

- **Gemini isolado não serve como fluxo do produto:** inventou nomes de laboratórios, unidades e serviços nos dois conjuntos.
- **Perguntas formais (seção 7.2):** RAG atual e multiagente empataram em qualidade; o multiagente custou ~1,8× tempo e tokens.
- **Perguntas coloquiais (seção 7.3, conjunto que o favorece):** o multiagente respondeu 3 perguntas que o RAG atual não respondeu ou errou, a ~3,3× o tempo e ~3,5× os tokens, com resultado instável entre execuções.
- **O Revisor não justificou seu custo:** nenhuma correção em 16 perguntas reais; detecta afirmações erradas, mas aprova respostas incompletas.

Recomendação preliminar: manter o **RAG atual** como fluxo padrão e avaliar, como próximo experimento, um **RAG com reformulação de consulta** (uma chamada para gerar subconsultas + uma para responder, sem Revisor), que concentra o ganho observado a um custo menor.

## 10. Referências

- Es et al. (2024), [RAGAs: Automated Evaluation of Retrieval Augmented Generation](https://aclanthology.org/2024.eacl-demo.16/).
- Manning et al., [Evaluation of ranked retrieval results](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html).
- [Sentence Transformers — Retrieve & Re-Rank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
- [Repositório e issues FCTE-Campus](https://github.com/Muniz2811/FCTE-Campus/issues).

# FCTE Campus · Assistente com fontes

Chat da base de conhecimento da FCTE/UnB Gama. A interface apresenta respostas, fontes utilizadas, trechos recuperados e o registro de cada consulta. Projeto acadêmico do Grupo 09, sem vínculo de serviço oficial com a UnB.

Este repositório contém **somente o chat e o RAG**. Mapa, GPS, favoritos, instalação e funcionamento offline foram retirados. A coleta e a visualização 3D permanecem no projeto separado [FcteMapping](https://github.com/Muniz2811/FcteMapping).

## Executar localmente

### macOS com chip Apple — instalação completa

Este caminho executa **interface, API, embeddings, reranker e Chroma no próprio Mac**. Somente a geração das respostas usa a API Gemini pela internet. Não é necessário instalar Docker, servidor Chroma ou banco externo.

Use o Terminal do macOS. Os exemplos colocam o projeto em `~/Projetos/FCTE-Campus`; se você já clonou em outro lugar, substitua esse caminho nos comandos. Execute os comandos na raiz do repositório, onde ficam `package.json` e a pasta `backend/`.

#### 1. Instalar Node e Python

Instale o [Homebrew](https://brew.sh/) se ainda não o tiver. Ao concluir a instalação, siga o trecho **Next steps** mostrado pelo instalador para disponibilizar `brew` no Terminal. Depois:

```bash
brew install git node@22 python@3.12
export PATH="$(brew --prefix node@22)/bin:$PATH"

node --version
npm --version
python3.12 --version
uname -m
```

Confira Node **22.12 ou superior**, Python **3.12.x** e arquitetura **arm64**. O tutorial usa Python 3.12 para manter o mesmo minor do Dockerfile. As fórmulas oficiais são [node@22](https://formulae.brew.sh/formula/node@22) e [python@3.12](https://formulae.brew.sh/formula/python@3.12).

O `export PATH` seleciona o Node instalado acima somente no terminal atual. Nos passos de inicialização ele aparece novamente para funcionar também em novas janelas. Se preferir, adicione essa mesma linha ao seu `~/.zshrc`.

#### 2. Baixar o projeto

Se ainda não clonou:

```bash
mkdir -p ~/Projetos
cd ~/Projetos
git clone https://github.com/Muniz2811/FCTE-Campus.git
cd FCTE-Campus
```

Se já tem o repositório, entre na pasta existente. Para atualizar, use `git pull --ff-only` quando não houver alterações locais pendentes. Não copie uma `.venv`, `node_modules` ou cache de outro computador: as dependências serão instaladas para o Mac.

#### 3. Instalar as dependências do sistema

Na raiz do projeto:

```bash
npm ci
python3.12 -m venv backend/.venv
./backend/.venv/bin/python -m pip install --upgrade pip
./backend/.venv/bin/python -m pip install -r backend/requirements.txt
./backend/.venv/bin/python -m pip check
```

O primeiro comando instala a interface. Os demais criam um ambiente Python isolado e instalam as versões do backend, incluindo PyTorch, Sentence Transformers e Chroma. O download pode demorar e ocupar alguns GB entre ambiente, modelos e caches.

Não é necessário ativar a `.venv`: os scripts `npm run rag:*` e `npm run dev:rag` encontram automaticamente `backend/.venv/bin/python` no macOS. Aqui usamos `npm`, sem o sufixo `.cmd` do Windows.

#### 4. Configurar a chave Gemini

Crie o arquivo somente se ele ainda não existir:

```bash
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
fi
nano backend/.env
```

Preencha a linha com a sua chave, sem colá-la no chat nem no Git:

```dotenv
GEMINI_API_KEY=SUA_CHAVE_AQUI
```

Mantenha as outras configurações do exemplo para uso local. `GEMINI_MODEL` é opcional e permite substituir o modelo configurado em `backend/config/rag.yaml`. No `nano`, salve com **Control + O**, confirme com **Enter** e saia com **Control + X**.

A chave fica somente no backend. Não crie variáveis `VITE_*` com ela. Depois de mudar `backend/.env`, reinicie a API. O servidor lê desse arquivo a chave e o modelo; configurações de hospedagem, como hosts e origens, devem ser exportadas no ambiente quando necessárias.

#### 5. Preparar os modelos e criar o banco vetorial

Ainda na raiz, execute nesta ordem, aguardando cada comando terminar:

```bash
npm run rag:prepare
npm run rag:index
npm run rag:check
```

| Comando | O que acontece |
|---|---|
| `rag:prepare` | Baixa os pesos do reranker na revisão fixada pelo projeto. |
| `rag:index` | Baixa/carrega o E5, vetoriza os chunks curados e grava a coleção Chroma e o manifesto. |
| `rag:check` | Abre o banco em outro processo, confere os vetores e executa uma consulta de verificação sem Gemini. |

Esses passos não usam a API Gemini. A primeira preparação exige internet para baixar modelos; consultas com geração e a comparação com Gemini também precisam de conexão. O projeto utiliza **CPU**, inclusive no chip Apple, conforme a configuração atual; não é preciso configurar Metal/MPS.

Ao final, confira a saída de `rag:check`: na base atual, são **37 fontes**, **174 chunks**, dimensão **384** e `reaberto_sem_ingestao: true`. O banco fica em `backend/data/index/chroma/`, com manifesto em `backend/data/index/manifesto.json`. Não apague essa pasta entre as execuções.

Os documentos já estão preparados no repositório. Não é necessário exportar páginas, refazer curadoria ou chunking para rodar a aplicação. O índice e os modelos são locais e não vêm pelo Git: cada integrante faz essa preparação uma vez no próprio computador.

#### 6. Iniciar a API — terminal 1

```bash
cd ~/Projetos/FCTE-Campus
export PATH="$(brew --prefix node@22)/bin:$PATH"
npm run dev:rag
```

Espere aparecer `Application startup complete` e o endereço `http://127.0.0.1:8001`. **Deixe esse terminal aberto.**

#### 7. Iniciar a interface — terminal 2

Abra outra aba ou janela do Terminal:

```bash
cd ~/Projetos/FCTE-Campus
export PATH="$(brew --prefix node@22)/bin:$PATH"
npm run dev
```

Abra **[http://127.0.0.1:5173](http://127.0.0.1:5173)**. O Vite encaminha as chamadas `/api/v1` para a API na porta 8001. Não abra `index.html` diretamente pelo Finder.

| Endereço | Uso |
|---|---|
| `http://127.0.0.1:5173` | Aplicação: conversa, métricas e comparação ao vivo. |
| `http://127.0.0.1:8001/api/v1/health` | Disponibilidade da base e da configuração Gemini. |
| `http://127.0.0.1:8001/docs` | Documentação interativa da API. |

#### 8. Conferir o funcionamento completo

Com os dois terminais abertos, em um terceiro terminal:

```bash
curl --fail http://127.0.0.1:8001/api/v1/health
```

A resposta deve conter `status: "ready"`, `generationConfigured: true`, `sources: 37` e `chunks: 174` para a base atual. `generationConfigured: true` confirma que uma chave foi carregada; a validade e a cota só são verificadas ao chamar o Gemini.

Na aplicação:

1. Em **Conversa**, pergunte: “Na biblioteca do Gama há lugar para estudar sozinho e em grupo?”. Confira a resposta, as fontes e os trechos recuperados.
2. Em **Métricas do RAG**, confira os resultados históricos, as explicações e o exemplo interativo. Abrir essa aba não faz chamadas ao Gemini.
3. Em **Comparar ao vivo**, envie a mesma pergunta aos dois sistemas. Confira as duas respostas, tempos e tokens; esse envio pode consumir duas chamadas Gemini. As métricas semânticas dependem da revisão guiada.

Para verificar apenas a recuperação pelo terminal, sem chamar o Gemini:

```bash
npm run rag:ask -- "Onde fica o laboratório COSMOS?" --json
```

#### Próximas vezes

Com dependências, modelos, `.env` e índice já preparados, basta repetir os passos **6 e 7**. Não é preciso reinstalar tudo nem vetorizar novamente. Se uma atualização alterar o corpus ou a configuração do índice, siga a mensagem do backend para reconstruí-lo.

Para parar, pressione **Control + C** em cada um dos dois terminais. Se quiser usar um `.env` já existente em outro caminho, informe-o explicitamente, sem copiar a chave:

```bash
npm run dev:rag -- --env-file /caminho/para/seu/arquivo.env
```

#### Alternativa: interface compilada e API no mesmo endereço

Pare os processos anteriores. Na raiz:

```bash
npm run build
npm run dev:rag
```

Abra **[http://127.0.0.1:8001](http://127.0.0.1:8001)**. A API também serve a interface de `dist/`, incluindo as três abas. Não é necessário manter o Vite aberto nessa opção. Após mudar o frontend, refaça o build; esse modo não tem atualização automática dos arquivos da interface.

#### Problemas comuns no Mac

| Sintoma | Como resolver |
|---|---|
| `brew: command not found` | Conclua o **Next steps** do instalador Homebrew e reabra o Terminal. |
| `npm: command not found` ou Node incompatível | Execute o `export PATH` do passo 1 e confira `node --version`. Use a versão exigida pelo projeto. |
| `ENOENT ... package.json` | Você está na pasta errada. Entre em `FCTE-Campus`, não em `backend` ou no projeto de coleta. |
| `Crie backend/.venv...` | Execute o passo 3 na raiz. O ambiente deve estar exatamente em `backend/.venv`. |
| `No matching distribution found for torch` ou erro de arquitetura | Confira `uname -m` e `python3.12 -c 'import platform; print(platform.machine())'`: ambos devem indicar `arm64`. Use Terminal e Python nativos do chip Apple, sem Rosetta, e crie a `.venv` com esse Python. Não altere as versões do RAG para contornar o erro. |
| Erro pedindo compilador/ferramentas Apple | Instale as Command Line Tools com `xcode-select --install`, conclua a instalação e repita o comando que falhou. |
| Download do Hugging Face falhou | Confira a conexão e repita `rag:prepare` ou `rag:index`, conforme a etapa interrompida. Não é necessário apagar os documentos ou o banco. |
| Reranker não preparado / índice ausente | Execute os três comandos do passo 5. |
| Interface informa backend indisponível | Confira se o terminal 1 continua aberto e consulte `/api/v1/health`. Se o servidor foi iniciado antes da criação do índice, reinicie-o. |
| Gemini não configurado, cota ou timeout | Confira `backend/.env`, reinicie a API e leia a mensagem devolvida. A saúde da base não garante que a chave tenha cota. |
| Porta 5173 ou 8001 ocupada | Procure outro terminal com o mesmo projeto e pare esse processo com Control + C. Fechar apenas a aba do navegador não encerra o servidor. |
| Alterações do frontend não aparecem na porta 8001 | Execute `npm run build` novamente ou use o Vite na porta 5173 durante o desenvolvimento. |
| Pouca memória ou lentidão | E5, reranker, PyTorch e Chroma usam memória local. Evite iniciar várias cópias do backend; a primeira consulta pode demorar mais ao carregar o reranker. |

Os comandos acima foram conferidos com os scripts do repositório e as instruções oficiais das dependências. A execução nativa em macOS ainda precisa ser validada pela equipe em um Mac; não foi executada no ambiente Windows utilizado para manter este README.

### Windows — PowerShell

Requisitos: Node 22.12+ e Python 3.12 ou 3.13. No PowerShell, na raiz do projeto:

```powershell
npm.cmd ci
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Preencha `GEMINI_API_KEY` em `backend/.env`. Não sobrescreva um ambiente já configurado. Em Linux/macOS, use `backend/.venv/bin/python`.

Na primeira execução, prepare os modelos e o índice:

```powershell
npm.cmd run rag:prepare
npm.cmd run rag:index
npm.cmd run rag:check
```

Esses comandos baixam os pesos fixados de E5/reranker e constroem o Chroma com os chunks curados já presentes no repositório. Não fazem chamadas ao Gemini. Se os modelos e o índice já existem, não é necessário repetir essa etapa.

Inicie os dois processos em terminais separados:

```powershell
# API: http://127.0.0.1:8001
npm.cmd run dev:rag
```

```powershell
# Interface: http://127.0.0.1:5173
npm.cmd run dev
```

O Vite encaminha `/api/v1` à API local. Também é possível fornecer explicitamente um arquivo de configuração existente, sem copiar a chave:

```powershell
npm.cmd run dev:rag -- --env-file ../coleta-fcte/.env
```

## Deploy em um único serviço

O `Dockerfile` da raiz reúne interface e API. A aplicação Python serve o chat em `/` e o backend em `/api/v1`, no mesmo domínio. Não é necessário outro servidor para o frontend ou para o Chroma.

O build instala PyTorch **CPU**, baixa os modelos, gera e confere o índice, e incorpora o frontend compilado. Não recebe a chave Gemini. Essa primeira construção exige internet e pode demorar devido aos pesos dos modelos.

```sh
docker build -t fcte-chat .
docker run --rm -p 8000:8000 --env-file backend/.env fcte-chat
```

Abra `http://localhost:8000`. Para hospedar online, selecione deploy por Docker usando o **Dockerfile da raiz**, configure a porta interna `8000` ou a variável `PORT` do provedor, e adicione estas variáveis no painel:

| Variável | Valor |
|---|---|
| `GEMINI_API_KEY` | Chave secreta da API Gemini |
| `GEMINI_MODEL` | Opcional; o padrão está em `backend/config/rag.yaml` |
| `RAG_ALLOWED_HOSTS` | `localhost,127.0.0.1,SEU-DOMINIO` — sem protocolo |
| `RAG_ALLOWED_ORIGINS` | `https://SEU-DOMINIO` — sem barra final |

Use `/api/v1/health` para verificar a disponibilidade. Nenhuma chave é enviada ao navegador. O contêiner usa um único worker, com uma consulta por vez para conter o consumo de memória; novas consultas simultâneas recebem uma mensagem para aguardar.

**A simplificação facilita o deploy, mas não reduz a memória exigida pelo E5 e pelo reranker.** O serviço precisa comportar ambos, PyTorch e Chroma. O build Docker deve ser validado no provedor/arquitetura escolhidos; não há garantia de execução em planos de 512 MB.

O índice inicial está dentro da imagem e reaparece ao recriar o contêiner. Alterações feitas em execução, logs e contexto entre perguntas não persistem sem armazenamento externo/volume. Os originais, chunks e avaliações continuam sendo a base para reconstruir o índice; o histórico das conversas não é usado como fonte factual.

## Fluxo do RAG

A navegação possui **Conversa**, **Métricas do RAG** e **Comparar ao vivo**. O painel histórico lê os artefatos preservados de `backend/avaliacao/resultados/semana3-llm-rag-20261112-v1`, com fórmulas, exemplos interativos, quatro cenários e limitações. Não recalcula os resultados antigos com respostas novas.

Na comparação ao vivo, a mesma pergunta é enviada em paralelo ao **RAG atual completo** e ao **mesmo Gemini sem documentos**, sem histórico nos dois braços. Cada envio pode consumir duas chamadas da API. Tempo, tokens disponíveis, disponibilidade e rastreabilidade documental são medidos; qualidade factual, relevância, completude, ausência e premissas exigem a revisão guiada. O gabarito é mostrado ao revisor e não é enviado como contexto ao modelo. Métricas sem julgamento ou denominador ficam pendentes ou N/A.

A primeira saída válida de cada execução é preservada. A interface permite repetir somente falhas técnicas; todas as tentativas continuam no histórico. A sessão agrega os contadores julgados, mostra a cobertura da revisão e permite exportar JSON com respostas, configurações, hashes dos prompts, tentativas e julgamentos. Sessões do navegador ficam em memória; os registros do servidor são privados em `backend/data/execucoes/comparacao-*.json`. Repetir uma pergunta como nova execução não torna a amostra independente.

Endpoints adicionais: `GET /api/v1/evaluation`, `POST /api/v1/comparison/rag` e `POST /api/v1/comparison/llm` (corpo `{ "text": "sua pergunta", "campus": "gama" }`). A comparação usa a mesma chave secreta do backend. O prompt e o contrato do braço isolado são compartilhados com o script histórico em `rag/consulta/llm_isolada.py`.

O Docker inclui apenas os três artefatos necessários ao painel. Como originais e extrações não entram nessa imagem, a rastreabilidade **completa** ao vivo fica N/A nesse deploy; os IDs e fontes continuam disponíveis para inspeção. Localmente, com esses arquivos presentes, a cadeia é conferida até o hash do original. Persistência continua sendo o ensaio histórico em processos novos; uma consulta HTTP não o substitui.

```text
Pergunta → E5 → Chroma + BM25 → RRF → reranker → seleção dos trechos
                                                     ↓
Chat com fontes ← validação dos vínculos de citação ← Gemini
```

O corpus atual contém 37 fontes indexadas e 174 chunks armazenados. O filtro temporal exclui os trechos de documentos históricos das consultas atuais. A busca e o reranker preservam a configuração existente; a interface não altera resultados, notas ou fontes.

Complementos de perguntas usam `previousRequestId` para recuperar o assunto da consulta anterior. Nova conversa limpa essa referência. Cancelar encerra a espera no navegador; uma chamada Gemini iniciada pode terminar e consumir cota. Não há informação de ocupação ao vivo nem cálculo de rotas.

## Organização e verificação

- `src/knowledge/`: contrato HTTP, estado da conversa, respostas e fontes.
- `src/evaluation/`: painel histórico, glossário, comparação real e revisão das métricas.
- `src/app/` e `src/design/`: interface responsiva e identidade UnB/FCTE.
- `backend/rag/`: ingestão, embeddings, Chroma, recuperação, geração e API.
- `backend/config/` e `backend/data/`: configuração, catálogo e corpus curado. Índice, pesos e execuções locais não são versionados.
- `backend/avaliacao/`: perguntas e resultados das avaliações realizadas; preservados.
- `Dockerfile`: build da interface e preparação do RAG para um serviço único.

```powershell
npm.cmd run build
npm.cmd test
npm.cmd run test:rag
npm.cmd run rag:check
```

Os testes existentes não chamam Gemini. A documentação técnica está em [backend/README.md](backend/README.md), e a metodologia e os resultados históricos em [Relatório da Semana 3](backend/RELATORIO_SEMANA_3_LLM_X_RAG.md).

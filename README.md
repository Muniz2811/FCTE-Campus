# FCTE Campus · Assistente com fontes

Chat da base de conhecimento da FCTE/UnB Gama. A interface apresenta respostas, fontes utilizadas, trechos recuperados e o registro de cada consulta. Projeto acadêmico do Grupo 09, sem vínculo de serviço oficial com a UnB.

Este repositório contém **somente o chat e o RAG**. Mapa, GPS, favoritos, instalação e funcionamento offline foram retirados. A coleta e a visualização 3D permanecem no projeto separado [FcteMapping](https://github.com/Muniz2811/FcteMapping).

**Banco vetorial no Supabase:** siga o [tutorial completo de migração](backend/supabase/README.md).
Há simulação antes do envio, reaproveitamento dos embeddings existentes e conferência do banco remoto.
O padrão continua sendo Chroma local até configurar `RAG_INDEX_BACKEND=supabase` no backend.

**Perfis de execução:** `RAG_PROFILE=full` mantém E5 + BM25/RRF + reranker para uso local.
O Docker usa `RAG_PROFILE=light` e Supabase por padrão: lê os textos, recupera por BM25 e gera com Gemini,
sem instalar PyTorch ou baixar modelos. A API do coleta-fcte permanece `POST /perguntar`.

**Mapeamento no RAG:** a base foi ampliada com quatro fichas da UAC/UED, contendo ambientes por andar e referências dos banheiros. Agora são **41 fontes e 214 chunks**. Os 174 trechos anteriores foram preservados. Consulte [importação dos mapas e atualização segura do Supabase](backend/README.md#alimentar-o-rag-com-os-mapas-da-coleta). O deploy antigo permanece com a base anterior até receber este código; a API nova abre o snapshot correspondente ao seu próprio catálogo/chunks, sem substituir a coleção usada pela versão anterior.

## Executar localmente

### Caminho rápido para o grupo — Mac com chip Apple

Depois de baixar o repositório, **abra `iniciar.command` com dois cliques**. Ou, no Terminal, dentro da pasta do projeto:

```bash
bash iniciar.command
```

Na primeira vez, o iniciador instala as dependências do projeto, prepara os modelos e o Chroma, compila a interface e abre **http://127.0.0.1:8001**. Se faltar a chave Gemini, ele abre `backend/.env` no editor e aguarda você preencher, salvar e confirmar no terminal. Não é preciso abrir dois terminais nem executar os comandos de preparação separadamente.

**Pré-requisito, uma vez por Mac:** Node e Python 3.12. Se ainda não estiverem instalados, instale [Homebrew](https://brew.sh/), siga seu **Next steps** e execute:

```bash
brew install node@22 python@3.12
```

Nas próximas vezes, abra o mesmo `iniciar.command`: ele reutiliza a preparação existente e refaz etapas quando os arquivos correspondentes mudam. A primeira execução exige downloads e pode demorar. O iniciador não instala programas do sistema automaticamente e não compartilha chaves entre integrantes.

Deixe o terminal aberto enquanto usa a aplicação e pressione **Control + C** para encerrar. Se o Finder não permitir executar o arquivo, use `bash iniciar.command` no Terminal. O fluxo de inicialização foi preparado para macOS, mas ainda precisa ser validado em um Mac da equipe.

O tutorial abaixo é a alternativa manual para desenvolvimento e diagnóstico.

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

A chave fica somente no backend. Não crie variáveis `VITE_*` com ela. Depois de mudar `backend/.env`, reinicie a API. O servidor lê desse arquivo a chave, o modelo e as credenciais de acesso; configurações de hospedagem, como hosts e origens, devem ser exportadas no ambiente quando necessárias.

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

Ao final, confira a saída de `rag:check`: na base atual, são **41 fontes**, **214 chunks**, dimensão **384** e `reaberto_sem_ingestao: true`. O banco fica em `backend/data/index/chroma/`, com manifesto em `backend/data/index/manifesto.json`. Não apague essa pasta entre as execuções.

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

A resposta deve conter `status: "ready"`, `generationConfigured: true`, `sources: 41` e `chunks: 214` para a base atual. `generationConfigured: true` confirma que uma chave foi carregada; a validade e a cota só são verificadas ao chamar o Gemini.

Na aplicação:

1. Em **Conversa**, pergunte: “Na biblioteca do Gama há lugar para estudar sozinho e em grupo?”. Confira a resposta, as fontes e os trechos recuperados.
2. Em **Métricas do RAG**, confira os resultados históricos, as explicações e o exemplo interativo. Abrir essa aba não faz chamadas ao Gemini.
3. Em **Comparar ao vivo**, envie a mesma pergunta aos três modos: Gemini isolado, RAG atual e RAG multiagente. Confira as respostas, tempos, tokens e a linha do tempo dos agentes; esse envio pode consumir de 3 a 7 chamadas Gemini. As métricas semânticas dependem da revisão guiada.
4. Em **Como funciona**, veja o caminho de uma pergunta em cada modo e o fluxo interno do multiagente, com os números medidos em 18/11/2026. Abrir essa aba não faz chamadas ao Gemini.

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

Abra **[http://127.0.0.1:8001](http://127.0.0.1:8001)**. A API também serve a interface de `dist/`, incluindo as quatro abas. Não é necessário manter o Vite aberto nessa opção. Após mudar o frontend, refaça o build; esse modo não tem atualização automática dos arquivos da interface.

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

### Integração com o orquestrador e acesso online

O contrato comum **v1.0** está implementado em `POST /perguntar` e documentado pelo OpenAPI em `/docs`. O chat independente mantém `POST /api/v1/chat`. Os dois endpoints usam o mesmo pipeline existente: E5, BM25/RRF, reranker, Chroma e Gemini.

| Responsabilidade | Serviço |
|---|---|
| Biblioteca, serviços estudantis gerais, saúde, acessibilidade e infraestrutura | FCTE-Campus · Grupo 09 |
| Cardápio, funcionamento e gratuidade do RU; disciplinas, pré-requisitos, matrícula e calendário acadêmico | RUmo · Grupo 04 |
| Localização de ambientes e ações para abrir o mapa | Ferramenta de mapa no `coleta-fcte` |

Requisição do contrato comum:

```json
{
  "pergunta": "A biblioteca oferece cabines individuais?",
  "contexto": { "campus": "gama", "data": "2026-11-13" },
  "max_trechos": 5
}
```

`contexto` também aceita `curso` e `previous_request_id` (UUID da consulta anterior deste RAG). Campus aceito: `gama`. A pergunta aceita até 1.000 caracteres. Aceitamos pedidos de 1 a 20 trechos por compatibilidade; o limite aplicado é o menor entre o pedido e os cinco configurados no nosso pipeline, informado em `max_trechos_aplicado`. O filtro de validade documental continua sendo o da busca existente; a data de contexto não substitui essa política.

A resposta preserva `grupo`, `resposta`, `encontrou_base`, `fontes` e `tempo_ms`, acrescentando `contrato_versao`, `dominio`, `status`, `request_id`, `base_version`, `afirmacoes`, `trechos` e metadados das fontes. Cada fonte citada possui `n`, `doc_id`, `chunk_id`, título, URL, seção, versão e trecho. Os índices `[n]` da resposta correspondem à lista de fontes daquele grupo.

| Status | Significado |
|---|---|
| `answered` | Resposta produzida com fontes. |
| `insufficient` | A consulta foi executada, mas faltou evidência suficiente. |
| `unavailable` | Falha de serviço, geração, cota ou conexão; o HTTP preserva o código da falha. |

Para hospedar a **API protegida e o chat independente online**, configure no ambiente do serviço:

```dotenv
RAG_REQUIRE_AUTH=true
RAG_API_TOKEN=TOKEN_ALEATORIO_COM_PELO_MENOS_32_CARACTERES
```

Use caracteres ASCII no token. Para gerar um segredo, execute `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'` no seu computador. Nunca use a chave Gemini como token interno.

- O orquestrador envia `Authorization: Bearer <RAG_API_TOKEN>` a `/perguntar`.
- O chat online, as métricas e a comparação são públicos, sem usuário, senha ou popup HTTP Basic. O token interno nunca entra no JavaScript ou no armazenamento do navegador. Variáveis antigas `RAG_WEB_USER` e `RAG_WEB_PASSWORD` são ignoradas e podem ser removidas do Render.
- `/api/v1/chat` e as duas rotas de comparação permitem uso direto pelo navegador. O health e os resultados históricos também são públicos.
- Dez tentativas com credenciais inválidas por IP em um minuto bloqueiam temporariamente a integração `/perguntar`; não bloqueiam o chat público.
- Localmente, sem `RAG_REQUIRE_AUTH=true`, a integração pode funcionar sem token. Hosts públicos ou o ambiente Render exigem token para `/perguntar`; configuração pública sem esse token impede a inicialização.

No backend do **coleta-fcte**, configure:

```dotenv
G09_API_URL=https://ENDERECO-DO-FCTE-CAMPUS
G09_API_TOKEN=MESMO_VALOR_DE_RAG_API_TOKEN
G09_TIMEOUT_SECONDS=120
```

`G09_API_URL` é o endereço base do **outro serviço**, sem `/perguntar`. Não aponte para o próprio orquestrador. Para desenvolvimento local, use `http://127.0.0.1:8001` e mantenha o `coleta-fcte` na porta 8000. O RUmo pode usar outra porta, por exemplo 8002, com `RUMO_API_URL` correspondente.

O orquestrador preserva os blocos e fontes de cada grupo e distingue ausência de evidência de indisponibilidade. Uma falha de um RAG não remove a resposta válida do outro. A implantação do nosso RAG continua sendo um serviço separado: adicionar esses campos no Render da coleta não hospeda os modelos lá.

O `Dockerfile` da raiz reúne interface e API. A aplicação Python serve o chat em `/` e o backend em `/api/v1`, no mesmo domínio. Não é necessário outro servidor para o frontend ou para o Chroma.

O build padrão é **light + Supabase**: instala apenas `backend/requirements-api.txt`, compila a interface e não instala NumPy, PyTorch, Transformers, Sentence Transformers ou Chroma. Não baixa pesos, não gera vetores e não acessa o banco ou o Gemini durante o build. As credenciais são fornecidas somente na execução.

No início do serviço, o perfil leve lê do Supabase somente texto e metadados dos chunks. Confere manifesto, hashes, IDs e conteúdo contra o corpus versionado, mantém esse snapshot em memória e refaz os filtros de aprovação, abrangência e validade a cada pergunta. Mudanças na base exigem atualizar os arquivos correspondentes e reiniciar/republicar a API. Vetores já existentes continuam preservados no Supabase.

```sh
docker build -t fcte-chat .
docker run --rm -p 127.0.0.1:8000:8000 --env-file backend/.env -e RAG_PROFILE=light -e RAG_INDEX_BACKEND=supabase -e RAG_REQUIRE_AUTH=false fcte-chat
```

Esse exemplo exige a conexão Supabase configurada em `backend/.env`. Para uma imagem completa com Chroma local, use `docker build --build-arg RAG_PROFILE=full --build-arg RAG_INDEX_BACKEND=chroma -t fcte-chat-local .` e execute essa imagem com `-e RAG_PROFILE=full -e RAG_INDEX_BACKEND=chroma`. Para full com Supabase, use somente `--build-arg RAG_PROFILE=full`. Ativar full em uma imagem construída como light não instala suas dependências; é necessário reconstruir a imagem.

Abra `http://localhost:8000`. O comando acima desativa autenticação somente para o teste na porta publicada em loopback. A imagem tem autenticação habilitada por padrão. Para hospedar online, selecione deploy por Docker usando o **Dockerfile da raiz**, mantenha `RAG_REQUIRE_AUTH=true` e as credenciais descritas acima, configure a porta interna `8000` ou a variável `PORT` do provedor, e adicione estas variáveis no painel:

| Variável | Valor |
|---|---|
| `GEMINI_API_KEY` | Chave secreta da API Gemini |
| `GEMINI_MODEL` | Opcional; o padrão está em `backend/config/rag.yaml` |
| `RAG_PROFILE` | `light` no Render Free; `full` para o pipeline completo local |
| `RAG_INDEX_BACKEND` | `supabase` |
| `SUPABASE_URL` | URL HTTPS do projeto, sem caminho |
| `SUPABASE_SECRET_KEY` | Chave secreta, somente no backend |
| `RAG_ALLOWED_HOSTS` | `localhost,127.0.0.1,SEU-DOMINIO` — sem protocolo |
| `RAG_ALLOWED_ORIGINS` | `https://SEU-DOMINIO` — sem barra final |

Use `/api/v1/health` para verificar a disponibilidade. Nenhuma chave é enviada ao navegador. O contêiner usa um único worker, com uma consulta por vez para conter o consumo de memória; novas consultas simultâneas recebem uma mensagem para aguardar.

O perfil light recupera por **BM25**, com os parâmetros lexicais existentes e no máximo dois chunks por fonte, até cinco no total. Não executa E5, RRF ou reranker. Isso mantém o RAG documental com citações, mas muda a recuperação: paráfrases e sinônimos precisam de uma nova avaliação. O painel avisa quando os resultados históricos pertencem a outra configuração. Não atribua as métricas do perfil full ao light.

### Render com Supabase e integração ao coleta-fcte

O fluxo de produção é `navegador → coleta-fcte (/api/chat) → FCTE-Campus (/perguntar) → Supabase + modelos + Gemini`. A coleta já possui o cliente desse contrato em `backend/consultas_rag.py` e o roteamento em `backend/assistente.py`; não é necessário copiar os documentos ou os modelos para aquele serviço. As fontes de RU/disciplinas continuam no RUmo.

**Capacidade:** o Render Free tem 512 MB de RAM e 0,1 CPU. Use `RAG_PROFILE=light` para esse deploy. O perfil full continua disponível para ambientes com memória suficiente. Consulte os [planos de computação](https://render.com/docs/compute-plans).

Em 16/11/2026, o perfil light foi executado localmente em Windows num ambiente isolado com apenas as dependências da API. Leu o Supabase real, executou três chamadas Gemini (contrato `/perguntar`, complemento do chat e comparação com a LLM), validou a resposta com o cliente do coleta-fcte e atingiu aproximadamente **59 MiB de pico de working set**. Não importou NumPy, PyTorch, Transformers, Sentence Transformers ou Chroma. Isso é uma conferência funcional e de memória local, não uma reavaliação das quinze perguntas nem medição do contêiner Linux. O build Docker e o deploy precisam ser validados no Render.

1. **Enviar o código ao GitHub.** O Render precisa receber o adaptador Supabase e este Dockerfile atualizado. Na raiz deste repositório, confira `git status`/`git diff` e faça commit/push para `Muniz2811/FCTE-Campus`. `.env`, pesos e índice local permanecem ignorados. Não execute `rag:index` ou `rag:migrate` como comando de inicialização no Render: a base já foi enviada ao Supabase.
2. **Criar ou atualizar o serviço.** No [Render Dashboard](https://dashboard.render.com), clique em **New → Web Service → conectar GitHub → Muniz2811/FCTE-Campus**. Use a branch `main`, nome como `fcte-campus-rag`, **Language/Runtime: Docker**, **Root Directory vazio**, **Dockerfile Path: ./Dockerfile**, **Docker Build Context: .** e plano **Free**. Deixe **Docker Command** vazio: o `CMD` já usa `uvicorn rag.api:app`, `0.0.0.0`, `$PORT` e um worker. Se o serviço já existe, basta atualizar o código, configurar light e reconstruir. Veja a [documentação Docker](https://render.com/docs/docker).
3. **Configurar Environment.** Use o domínio real que o Render atribuir ao serviço. O exemplo abaixo pressupõe `fcte-campus-rag.onrender.com`; substitua-o se o endereço for diferente. Não escreva esses segredos no GitHub.

```dotenv
RAG_PROFILE=light
RAG_INDEX_BACKEND=supabase
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_SECRET_KEY=SUA_CHAVE_SECRET_DO_SUPABASE
GEMINI_API_KEY=SUA_CHAVE_GEMINI
GEMINI_MODEL=gemini-3.5-flash-lite
RAG_REQUIRE_AUTH=true
RAG_API_TOKEN=TOKEN_ALEATORIO_COM_32_OU_MAIS_CARACTERES
RAG_ALLOWED_HOSTS=fcte-campus-rag.onrender.com,localhost,127.0.0.1
RAG_ALLOWED_ORIGINS=https://fcte-campus-rag.onrender.com
```

Gere o token no seu computador, por exemplo com `.\backend\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"` no PowerShell. No Mac: `./backend/.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`. O token da integração é diferente da chave Gemini e da chave Supabase. Use caracteres ASCII no token. Preserve o modelo Gemini que você já validou se ele for diferente do exemplo.

4. **Health check e deploy.** Configure **Health Check Path: /api/v1/health**. Após enviar as alterações para o GitHub, use **Environment → Save, rebuild, and deploy** ou **Manual Deploy → Clear build cache & deploy**, garantindo que a imagem seja reconstruída sem os modelos. Abra `https://SEU-DOMINIO/api/v1/health`: o esperado é HTTP 200, `status: ready`, `vectorStore: supabase`, `retrievalProfile: light`, `retrievalMethod: bm25`, `vectorSearchEnabled: false`, `rerankerEnabled: false`, `sources: 41` e `chunks: 214` na versão atual. `generationConfigured: true` informa presença da chave; uma pergunta real é necessária para conferir Gemini. O chat, a comparação e o health são públicos; somente a integração `/perguntar` pede token.
Se o log mostrar `RAG pronto` e o health check retornar **400**, confira `RAG_ALLOWED_HOSTS`: deve conter o domínio real, sem `https://` ou caminhos. A API acrescenta automaticamente `RENDER_EXTERNAL_HOSTNAME`, informado pelo Render, à lista de hosts permitidos. Domínios personalizados devem ser incluídos manualmente. A raiz do chat deve abrir sem login; mantenha o health check em `/api/v1/health`. Não é necessário liberar todos os hosts com `*`. Referências: [health checks](https://render.com/docs/health-checks) e [variáveis do Render](https://render.com/docs/environment-variables).

5. **Ligar o serviço existente coleta-fcte.** No Render, abra o serviço **coleta-fcte → Environment → Add Environment Variable** e configure:

```dotenv
G09_API_URL=https://fcte-campus-rag.onrender.com
G09_API_TOKEN=MESMO_VALOR_EXATO_DE_RAG_API_TOKEN
G09_TIMEOUT_SECONDS=120
```

Use a URL real do **FCTE-Campus**, sem `/perguntar`, sem `/api/v1` e sem apontar para o próprio coleta-fcte. O cliente já acrescenta `/perguntar` e envia `Authorization: Bearer ...`. Salve com **Save and deploy** para reiniciar a coleta com as variáveis. Não altere `RUMO_API_URL`, `RUMO_API_TOKEN` ou as configurações de coleta para fazer esta conexão. As variáveis `G09_*` já estão previstas no `render.yaml` daquele projeto.

6. **Validar a integração.** Em `https://ENDERECO-DA-COLETA/api/chat/estado`, `grupo09: true` confirma somente que a URL foi configurada. No chat da coleta, pergunte **“Na biblioteca do Gama há cabines individuais e mesas para estudar em grupo?”**. Essa pergunta exige conteúdo documental; “Onde fica a I10?” pode ser respondida pela ferramenta do mapa e não comprova a chamada ao RAG. A resposta documental deve vir do Grupo 09 com citações e fontes. Nos logs do FCTE-Campus, confira o `POST /perguntar` com HTTP 200. A raiz do FCTE-Campus também oferece o chat independente e a comparação, públicos e sem senha.

O navegador da coleta fala com o próprio backend; é esse backend que chama o RAG. Por isso não é necessário colocar o token no frontend, apontar o Vite para o serviço remoto ou liberar CORS da coleta para essa comunicação.

Para conferir `/perguntar` diretamente no PowerShell, sem gravar o token no histórico do terminal:

```powershell
$ragUrl = 'https://SEU-DOMINIO-DO-RAG'
$ragSecret = Read-Host 'Token RAG_API_TOKEN' -AsSecureString
$ragToken = [System.Net.NetworkCredential]::new('', $ragSecret).Password
$ragBody = @{ pergunta = 'Na biblioteca do Gama ha cabines individuais?'; contexto = @{ campus = 'gama' }; max_trechos = 5 } | ConvertTo-Json -Depth 4
try {
    Invoke-RestMethod -Method Post -Uri "$ragUrl/perguntar" -Headers @{ Authorization = "Bearer $ragToken" } -ContentType 'application/json' -Body $ragBody -TimeoutSec 180
} finally {
    Remove-Variable ragToken, ragSecret -ErrorAction SilentlyContinue
}
```

Espere `grupo: grupo09`, `status: answered` e fontes compatíveis. `insufficient` significa consulta executada sem evidência suficiente; não equivale a indisponibilidade.

| Sintoma | Diagnóstico |
|---|---|
| `Invalid host header` / HTTP 400 | Incluir o domínio real em `RAG_ALLOWED_HOSTS`, sem `https://`. |
| Não inicia / erro de autenticação | `RAG_REQUIRE_AUTH=true`, token com 32+ caracteres ASCII. O chat não exige senha. |
| Health HTTP 503 | Conferir Supabase, versão do corpus e cache offline E5 nos logs. |
| Integração HTTP 401/403 | `G09_API_TOKEN` precisa ser idêntico a `RAG_API_TOKEN`; não usar chave Gemini. |
| Integração HTTP 404 | URL base errada ou `/perguntar` foi acrescentado duas vezes. |
| Exit 137 / memória excedida | A instância não comportou os modelos; trocar o banco não resolve RAM. |
| Health funciona, mas a pergunta falha | A primeira consulta ainda carrega o reranker; conferir memória, tempo e erro Gemini. |
| Supabase HTTP 401/403/404 | Chave do projeto e SQL da migração; é uma autenticação diferente do token do orquestrador. |

No Free, o serviço suspende após 15 minutos sem tráfego, o que pode consumir parte do timeout da coleta na primeira consulta. Os arquivos de `data/execucoes/` são temporários no Render sem disco persistente; o armazenamento remoto dos registros de consultas ainda não foi implementado. Reiniciar pode perder o contexto de continuação de uma conversa. A base vetorial permanece no Supabase. Consulte [limitações do Free](https://render.com/docs/free).

O índice inicial está dentro da imagem e reaparece ao recriar o contêiner. Alterações feitas em execução, logs e contexto entre perguntas não persistem sem armazenamento externo/volume. Os originais, chunks e avaliações continuam sendo a base para reconstruir o índice; o histórico das conversas não é usado como fonte factual.

## Fluxo do RAG

A navegação possui **Conversa**, **Métricas do RAG**, **Comparar ao vivo** e **Como funciona**. O painel histórico lê os artefatos preservados de `backend/avaliacao/resultados/semana3-llm-rag-20261112-v1`, com fórmulas, exemplos interativos, quatro cenários e limitações. Não recalcula os resultados antigos com respostas novas. A aba **Como funciona** mostra números fixos da rodada de 18/11/2026, com origem em `src/evaluation/route-data.ts`.

Na comparação ao vivo, a mesma pergunta é enviada, em sequência, ao **Gemini sem documentos**, ao **RAG atual completo** e ao **RAG multiagente** (Pesquisador → Redator → Revisor, ver `backend/RELATORIO_MULTIAGENTE.md`), sem histórico entre os braços. Cada envio pode consumir de 3 a 7 chamadas da API. Tempo, tokens disponíveis, disponibilidade e rastreabilidade documental são medidos; qualidade factual, relevância, completude, ausência e premissas exigem a revisão guiada. O gabarito é mostrado ao revisor e não é enviado como contexto ao modelo. Métricas sem julgamento ou denominador ficam pendentes ou N/A.

A primeira saída válida de cada execução é preservada. A interface permite repetir somente falhas técnicas; todas as tentativas continuam no histórico. A sessão agrega os contadores julgados, mostra a cobertura da revisão e permite exportar JSON com respostas, configurações, hashes dos prompts, tentativas e julgamentos. Sessões do navegador ficam em memória; os registros do servidor são privados em `backend/data/execucoes/comparacao-*.json`. Repetir uma pergunta como nova execução não torna a amostra independente.

Endpoints adicionais: `GET /api/v1/evaluation`, `POST /api/v1/comparison/rag`, `POST /api/v1/comparison/llm` e `POST /api/v1/comparison/multiagente` (corpo `{ "text": "sua pergunta", "campus": "gama" }`). `POST /api/v1/multiagent` executa só o fluxo multiagente e, como `/perguntar`, exige token Bearer em deploy. A comparação usa a mesma chave secreta do backend. O prompt e o contrato do braço isolado são compartilhados com o script histórico em `rag/consulta/llm_isolada.py`.

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

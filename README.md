# FCTE Campus · Assistente com fontes

Chat da base de conhecimento da FCTE/UnB Gama. A interface apresenta respostas, fontes utilizadas, trechos recuperados e o registro de cada consulta. Projeto acadêmico do Grupo 09, sem vínculo de serviço oficial com a UnB.

Este repositório contém **somente o chat e o RAG**. Mapa, GPS, favoritos, instalação e funcionamento offline foram retirados. A coleta e a visualização 3D permanecem no projeto separado [FcteMapping](https://github.com/Muniz2811/FcteMapping).

## Executar localmente

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

```text
Pergunta → E5 → Chroma + BM25 → RRF → reranker → seleção dos trechos
                                                     ↓
Chat com fontes ← validação dos vínculos de citação ← Gemini
```

O corpus atual contém 37 fontes indexadas e 174 chunks armazenados. O filtro temporal exclui os trechos de documentos históricos das consultas atuais. A busca e o reranker preservam a configuração existente; a interface não altera resultados, notas ou fontes.

Complementos de perguntas usam `previousRequestId` para recuperar o assunto da consulta anterior. Nova conversa limpa essa referência. Cancelar encerra a espera no navegador; uma chamada Gemini iniciada pode terminar e consumir cota. Não há informação de ocupação ao vivo nem cálculo de rotas.

## Organização e verificação

- `src/knowledge/`: contrato HTTP, estado da conversa, respostas e fontes.
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

# FCTE Campus

PWA do módulo espacial do Grupo 09, com mapa como tela principal e identidade UnB/FCTE. Projeto acadêmico, sem vínculo de serviço oficial com a Universidade.

Repositório unificado: **frontend React em `src/` e backend RAG em `backend/`**. O backend foi incorporado do projeto `unb-gama-rag`; o código de ingestão, os dados curados e as avaliações foram preservados. A ferramenta de coleta/visualização 3D continua no repositório separado [FcteMapping](https://github.com/Muniz2811/FcteMapping).

## Rodar localmente

Node **22.12 ou superior**. Na pasta deste projeto:

```powershell
npm ci
npm run dev
```

Abra a URL impressa pelo Vite, normalmente **http://127.0.0.1:5173/**. Não é necessário configurar chave de API.

```powershell
npm test          # catálogo, busca, favoritos e contrato HTTP do assistente
npm run build    # TypeScript + produção + service worker
npm run preview  # prévia do build em http://127.0.0.1:4173/
```

O service worker só é habilitado no build de produção. Instalação e GPS exigem HTTPS ou localhost. Para acessar o dev server pelo celular na mesma rede, use `npm run dev -- --host 0.0.0.0`; o IP HTTP do computador permite ver a interface, mas não oferece todas as capacidades de PWA/GPS. Para essas capacidades no celular, use uma hospedagem HTTPS.

## O que funciona

- Mapa OpenStreetMap/Leaflet com os **14 pontos** do mapeamento da equipe, detalhes e vínculo com a origem.
- Busca sem distinção de acentos/caixa, filtros por categoria e estados vazios.
- Favoritos locais, separados por dispositivo/navegador. Armazenamento bloqueado gera aviso; não derruba o app.
- Link compartilhável por local (`#place=MAP-001-P014`) e abertura do destino no Google Maps.
- Consulta pontual ao GPS, com permissão solicitada pelo navegador e indicação de precisão. Não há rastreamento nem persistência da posição.
- Painel lateral no desktop, painel expansível no celular, navegação por teclado, movimentos reduzidos e animações de seleção/transição.
- Manifest, ícones, instruções de instalação e atualização mediante escolha. Shell, catálogo e favoritos acessíveis offline depois da primeira visita concluída.

O mapa-base depende de internet; não é baixado para uso offline. Tiles seguem a [política do OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/), com atribuição visível e sem precache. Ao mover o mapa ou usar GPS, o provedor de tiles recebe as requisições correspondentes à área exibida; a aplicação não envia a posição para um backend próprio. Links externos abrem somente o destino público selecionado.

O **assistente está conectado ao RAG local** por uma API HTTP. E5 e Chroma executam no computador; o Gemini precisa de internet e de uma chave no backend. Há respostas com fontes, trechos recuperados, indicação de informação insuficiente, cancelamento da espera e erros reais de rede/cota. Não há resposta simulada, rota calculada, previsão de ônibus ou ocupação atual de salas.

### Preparar o backend pela primeira vez

Python **3.12 ou 3.13**. Execute na raiz deste repositório, no PowerShell:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Preencha **`GEMINI_API_KEY` somente em `backend/.env`**. Não sobrescreva um `.env` já configurado. Em Linux/macOS, use `backend/.venv/bin/python` no lugar do executável Windows e `cp` para a cópia.

Depois prepare os modelos e o banco:

```powershell
npm.cmd run rag:prepare
npm.cmd run rag:index
npm.cmd run rag:check
```

Essas etapas baixam os pesos do reranker/E5 e constroem o Chroma a partir dos chunks curados incluídos no repositório. Exigem internet no primeiro preparo, mas não chamam Gemini. O banco em `backend/data/index/` e os pesos em `backend/.cache/` são locais e ficam fora do Git. Não é preciso baixar novamente as páginas institucionais para reconstruir o índice com os chunks já preparados.

Se o índice e os modelos já existem, passe direto para iniciar os dois processos. O ambiente e o índice do computador original foram preservados durante a integração.

### Iniciar o frontend e o chat

Dois terminais, ambos na raiz `fcte-campus`:

```powershell
# Terminal 1: backend em http://127.0.0.1:8001
npm.cmd run dev:rag
```

```powershell
# Terminal 2: frontend em http://127.0.0.1:5173
npm.cmd run dev
```

Abra a aba **Assistente**. O proxy do Vite encaminha `/api/rag/chat` e `/api/rag/health` para `/api/v1/chat` e `/api/v1/health`, sem expor a chave.

Neste workspace, também é possível reutilizar a chave da coleta explicitamente, sem copiá-la:

```powershell
npm.cmd run dev:rag -- --env-file ../coleta-fcte/.env
```

Os caminhos de `--env-file` nos comandos npm são relativos ao terminal. Os comandos entram em `backend/` automaticamente. Para usar outro ambiente Python, defina `RAG_PYTHON` com seu executável.

O chat utiliza **37 fontes e 174 chunks armazenados**, busca E5 + BM25/RRF, reranker multilíngue local e Gemini. O filtro temporal exclui 18 chunks de um edital histórico das consultas atuais. Os marcadores do mapa não fornecem automaticamente salas ou rotas. Complementos podem enviar `previousRequestId`, permitindo consultar o assunto de um registro anterior da mesma base. Isso é contexto curto, não memória ilimitada nem evidência factual. Iniciar uma nova conversa limpa a referência. Cancelar interrompe a espera, mas uma chamada Gemini já iniciada pode terminar e consumir cota.

As execuções privadas ficam em `backend/data/execucoes/`, fora do Git. O [relatório da Semana 3](backend/RELATORIO_SEMANA_3_LLM_X_RAG.md) explica o fluxo, as métricas e a comparação real com a LLM isolada. A [documentação do backend](backend/README.md) detalha a ingestão e a organização interna.

Para outra porta de backend, configure `RAG_API_TARGET` no ambiente do Vite. O proxy existe no dev e no preview; um futuro deploy precisa de API hospedada/reverse proxy. Não há deploy nesta integração local.

## Dados e arquitetura

```text
src/
  app/              composição e estado de navegação
  campus/           domínio, busca, snapshot público e apresentação do mapa
  favorites/        persistência versionada de IDs e estado da interface
  knowledge/        contrato, chat e adaptador HTTP do RAG local
  installation/     instalação, conectividade e atualização
  design/           tokens, marca, ícones e estilos
public/             ícones próprios para navegador e instalação
scripts/            importação e ferramentas de manutenção
backend/
  rag/              ingestão, armazenamento, consulta e API Python
  config/           modelos, parâmetros e entidades
  data/             catálogo, texto extraído, chunks e dados locais ignorados
  avaliacao/        gabarito e resultados medidos
  scripts/          comandos de ingestão, índice, API e avaliação
data/imports/       exportação pública dos pontos do campus
```

Domínio e busca não dependem de React, Leaflet ou navegador. O contrato `CampusAssistant` separa pergunta, resposta e evidências do transporte. O adaptador `knowledge/infrastructure/http-assistant.ts` chama a API local; segredos permanecem no servidor. O contrato do orquestrador comum ainda precisará ser acordado e versionado entre os grupos.

O build usa um snapshot versionado em `src/campus/infrastructure/campus.json`; não depende das pastas vizinhas. A exportação pública original da equipe está incluída em `data/imports/campus/evidencias.json`. Para atualizar:

```powershell
npm run import:campus
# Ou informe outro arquivo no mesmo formato:
npm run import:campus -- C:\caminho\evidencias.json
```

O importador preserva os 14 IDs, descrições e associações, registra hash SHA-256 e data da exportação, rejeita IDs duplicados e coordenadas fora da região do campus Gama. `eligibleForPilot` é elegibilidade para o piloto RAG, não comprovação de revisão humana. Nomes originais, inclusive ambíguos, são preservados. Associações candidatas ao UED não são apresentadas como definitivas. A Praça Solar não foi fundida com a ficha independente da Praça da FCTE.

## Hospedar depois

Frontend estático: comando de build `npm ci && npm run build`, pasta de saída `dist`. Publique em um serviço HTTPS. Em um subdiretório, configure a base **antes** do build:

```powershell
$env:BASE_PATH = '/fcte-campus/'
npm run build
Remove-Item Env:\BASE_PATH
```

Base do Vite, início/escopo do manifest e fallback do service worker usam o mesmo prefixo. Sirva `index.html` nas navegações internas dessa base. Não sirva `sw.js` com cache imutável. Não há deploy nem push automático neste projeto.

## Validação e ferramentas

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run test:rag
npm.cmd run rag:check
```

Os testes existentes do backend não chamam Gemini. A avaliação comparativa real é um comando separado e consome cota, como documentado no relatório. O remoto original do módulo RAG é [joaocarvv/unb-gama-rag](https://github.com/joaocarvv/unb-gama-rag); sua integração neste repositório preserva os registros históricos, incluindo caminhos referentes à execução anterior à migração.

Os testes focam comportamentos que podem perder dados ou retornar locais incorretos; não há testes de aparência. O build gera e permite inspecionar manifest, ícones e precache. Instalação, recarga offline e aparência em um celular real ainda precisam de conferência manual.

Ícones PNG já estão incluídos; para regenerá-los, execute `scripts/generate-icons.py` em Python com Pillow instalado. Decisões e plano desta versão estão em [DESIGN.md](DESIGN.md) e [PLAN.md](PLAN.md).

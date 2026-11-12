# FCTE Campus PWA · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** entregar a primeira versão funcional do PWA de mapa do campus.

**Architecture:** domínio e casos de uso TypeScript independentes da interface; React compõe as funcionalidades; Leaflet e armazenamento do dispositivo são adaptadores. O assistente usa uma porta com disponibilidade explícita, sem Gemini no navegador.

**Tech Stack:** React, TypeScript, Vite, Leaflet, Motion, vite-plugin-pwa, Vitest.

**Spec:** [DESIGN.md](DESIGN.md), aprovado pelo usuário. Execução nativa nesta sessão; decisões de implementação já delegadas.

## Global Constraints

- Preservar os 14 IDs e a procedência do KML; não interpretar elegibilidade como revisão humana.
- O RAG estará indisponível até o backend real existir; não simular fontes ou respostas.
- Não precachear tiles OSM nem dados pessoais; atribuição cartográfica visível.
- Layout utilizável a partir de 360 px, teclado e movimento reduzido.
- Não usar o Git antigo da raiz nem modificar outros projetos.

## Review Focus

1. Coordenadas invertidas, IDs duplicados ou pontos inválidos devem ser rejeitados pelo importador/catálogo.
2. Busca sem acentos e filtros compostos devem continuar corretos após limpar ou selecionar.
3. Favoritos inválidos/armazenamento bloqueado não podem derrubar a interface.
4. Geolocalização recusada e tiles ausentes mantêm lista e fichas acessíveis.
5. PWA atualiza com consentimento, abre estrutura offline e não cacheia serviços de mapas ou conhecimento.

## Task 1 · Catálogo, domínio e busca

**Files:** `package.json`, configurações Vite/TypeScript, `scripts/import-campus.mjs`, `src/campus/domain/place.ts`, `src/campus/application/search-places.ts`, `src/campus/infrastructure/catalog.ts`, snapshot `src/campus/infrastructure/campus.json`.

**Interfaces:** `Place` contém ID, nome, tipo, coordenada nomeada, fonte, elegibilidade e associação; `searchPlaces(places, {query, category})` retorna os locais que atendem aos critérios.

- [x] Criar Git próprio e configuração de dependências compatível com o Node disponível.
- [x] Escrever casos que falhem para validação de coordenadas, busca sem acentos, filtro e ausência.
- [x] Importar os 14 pontos públicos com IDs e origem; implementar validação e busca.
- [x] Executar os casos e a verificação de tipos.

## Task 2 · Favoritos e contrato do assistente

**Files:** `src/favorites/application/favorites.ts`, `src/favorites/infrastructure/browser-favorites.ts`, `src/knowledge/application/assistant.ts`, `src/knowledge/infrastructure/unavailable-assistant.ts`.

**Interfaces:** favoritos leem/salvam somente IDs versionados; a porta do assistente retorna disponibilidade e, futuramente, resposta com fontes.

- [x] Escrever casos que falhem para persistência inválida, IDs desconhecidos e indisponibilidade do conhecimento.
- [x] Implementar adaptadores pequenos e estados de falha previsíveis.
- [x] Executar os casos sem banco, rede ou API paga.

## Task 3 · Interface de mapa e exploração

**Files:** `src/app/*`, `src/campus/presentation/*`, `src/favorites/presentation/*`, `src/knowledge/presentation/*`, `src/design/*`.

**Interfaces:** provedor de exploração compartilha seleção, busca e favoritos; `CampusMap` recebe locais e seleção e emite seleção, sem regras de negócio.

- [x] Ler as skills de frontend, composição React e acessibilidade pertinentes.
- [x] Implementar tokens, navegação, busca, filtros, cards de locais, mapa, ficha e assistente indisponível.
- [x] Implementar painéis mobile com alternativa a arraste, animações interrompíveis, foco e atalhos de fechamento.
- [x] Tratar GPS negado, mapas sem conexão, armazenamento indisponível e estados vazios.
- [x] Conferir tipos/build e revisar a interface em tamanhos desktop e mobile quando as ferramentas permitirem.

## Task 4 · Instalação, offline e atualização

**Files:** `vite.config.ts`, `public/*`, `src/installation/*`, manifest gerado e instruções no `README.md`.

**Interfaces:** instalação expõe disponibilidade real do navegador; atualização solicita recarga; offline preserva catálogo e estrutura.

- [x] Configurar escopo/base do app e assets próprios, com ícones de instalação.
- [x] Registrar service worker em produção com atualização por prompt; sem rotas de cache para OSM, GPS ou RAG.
- [x] Gerar o build e verificar manifest, ícones, precache e fallback de navegação.
- [x] Atualizar README e AGENTS com execução, estrutura real e limites.

## Task 5 · Conferência final

- [x] Executar testes de comportamento, TypeScript e build de produção.
- [x] Fazer revisão independente de integração conforme a skill de execução.
- [x] Corrigir problemas materiais e registrar limitações verificadas; entregar URL local e comandos de execução.

Não criar commits automaticamente como parte desta sessão. O repositório próprio será inicializado; publicação e integração RAG permanecem etapas posteriores.

## Registro da execução

- Catálogo público importado: 14 pontos, sem modificar a coleta ou o piloto RAG.
- 7 verificações de comportamento passaram; TypeScript e build de produção passaram.
- Mapa separado em chunk sob demanda; somente a fonte latina local entra no build.
- Repositório próprio verificado em feat/pwa-campus, sem commits ou push.
- Decisão: usar este plano como registro, sem duplicar arquivos temporários de controle.
- Limite de verificação: ferramenta de navegador interrompida; aparência mobile, instalação e recarga offline ainda exigem conferência manual.
- Revisão independente: nenhum achado crítico; corrigidos os dois importantes (rolagem herdada na ficha e atribuição encoberta no mobile). O espaço do painel expandido considera as áreas seguras; a atribuição fica acima dele. A rolagem é reiniciada na troca de conteúdo e ao concluir a saída animada.
- Ajustes menores: troca de hash limpa filtros incompatíveis; falhas parciais de tiles permanecem indicadas até nova tentativa. O painel recolhido usa um resumo próprio e remove os controles ocultos da navegação por teclado. Navegação de detalhes usa histórico e restauração de foco após a transição.
- Reavaliação: aparência, teclado virtual, leitor de tela e ciclo de instalação/atualização/offline continuam sem validação em navegador; backend/RAG, rotas e transporte estão fora desta entrega conforme o escopo aprovado.
- Evidência final: 7 testes passaram; TypeScript/build passaram; HTTP 200 para página, manifest e service worker; SHA-256 do catálogo confere com a exportação pública; 52 skills/1.027 arquivos íntegros. Build adicional com prefixo /fcte-campus/ gerado e conferido, saída temporária removida.

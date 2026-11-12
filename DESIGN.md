# FCTE Campus · proposta da primeira versão

**Data:** 10/11/2026. **Situação:** aprovada pelo usuário para implementação.

## Objetivo

Criar o aplicativo do módulo espacial do Grupo 09 para ajudar estudantes a encontrar locais do campus Gama pelo celular. A experiência será centrada em um mapa e inspirada na organização do Waze, com identidade UnB/FCTE, interação fluida e instalação como PWA. O RAG será integrado quando o mecanismo real estiver disponível.

O usuário definiu o produto, a referência visual, a prioridade mobile, as animações, o PWA e a futura integração RAG. As escolhas de bibliotecas e a organização abaixo são propostas técnicas do implementador.

## Situação existente

- `../coleta-fcte`: aplicativo de coleta independente, com revisão humana e armazenamento próprio.
- `../unb-gama-rag`: cinco HTMLs e um KML preparados em 79 chunks, com embeddings E5 de 384 dimensões. Banco vetorial, recuperação e geração fundamentada ainda não foram implementados.
- O inventário exportado contém 14 pontos do KML. Onze entraram nos chunks do piloto. Há dois laboratórios sem identificação; a associação de entradas ao UED permanece candidata.
- `../residencia-grupo-9`: documentação, identidade visual já adotada e evidências públicas. RU e disciplinas são frente do Grupo 04.
- Este diretório contém somente skills e preparação; ainda não há aplicação, dependências de frontend ou Git próprio.

## Abordagens consideradas

| Abordagem | Vantagem | Custo ou limitação | Decisão proposta |
|---|---|---|---|
| React + TypeScript + Vite, com backend separado por contrato | Adequado ao mapa interativo, PWA, hospedagem estática e evolução independente do RAG Python | O backend será integrado explicitamente | Adotar |
| Next.js com frontend e rotas de servidor | Útil quando renderização de servidor e rotas desse framework forem necessárias | Acrescenta uma camada de servidor sem necessidade demonstrada nesta primeira versão | Reservar para outra necessidade |
| Estender o frontend do coletor | Reaproveita a aplicação existente | Mistura cadastro de evidências com navegação do estudante e dificulta a evolução independente | Manter como projeto separado |

Escolha técnica proposta: React, TypeScript estrito, Vite e PWA com `vite-plugin-pwa`. Leaflet mantém compatibilidade com os marcadores existentes e permite um mapa real sem exigir conta de provedor comercial. Motion for React será usado nas transições de componentes; CSS cuidará de feedbacks simples. Não carregar engines 3D, ferramentas de vídeo ou múltiplas bibliotecas de animação no bundle sem uma função concreta.

## O que a primeira versão entregará

1. Mapa real do campus com os 14 marcadores existentes, enquadramento inicial e seleção sincronizada.
2. Busca local por nomes e termos documentados, filtros por tipo e estados explícitos de ausência.
3. Ficha do local com nome, identificação disponível, procedência e limitações; informações desconhecidas permanecem desconhecidas.
4. Favoritos no dispositivo e navegação entre explorar, salvos e assistente.
5. Localização opcional, solicitada somente ao tocar no controle correspondente, para centralizar o mapa. O GPS não determina prédio, andar, rota ou disponibilidade de espaço.
6. Interface responsiva, animações, teclado e controle de movimento reduzido.
7. Manifest, ícones, service worker, aviso de atualização e orientações de instalação adequadas ao navegador.
8. Contratos e adaptadores preparados para o RAG, com estado indisponível honesto até haver backend real.

Não serão implementados nesta primeira versão: cálculo próprio de rotas, navegação curva a curva, estimativas de chegada, ocupação em tempo real, horários de ônibus, caronas, contas individuais, escrita no banco do coletor ou execução do pipeline RAG. São evoluções com dependências de dados próprias.

## Experiência e direção visual

### Tela inicial

O mapa é a superfície principal, sem uma landing page antes dele. Um cabeçalho compacto apresenta a marca FCTE Campus e a busca. Controles flutuantes permitem aproximar, afastar, centralizar e reenquadrar. A atribuição cartográfica permanece visível e não fica sob os painéis.

No celular, busca e filtros ficam no topo; um painel inferior apresenta locais, favoritos ou a ficha selecionada. A navegação inferior terá três destinos: **Explorar**, **Salvos** e **Assistente**. No desktop, as mesmas funções ocupam um painel lateral, mantendo o mapa amplo.

```text
CELULAR                           DESKTOP
┌───────────────────────┐         ┌──────────────┬───────────────────┐
│ FCTE Campus           │         │ marca/busca  │                   │
│ Buscar no campus      │         │ filtros     │       mapa        │
│ [tipos de locais]     │         │ resultados  │                   │
│                       │         │ ou ficha    │   controles       │
│         mapa          │         │             │                   │
│                 GPS   │         │ navegação   │ atribuição        │
│ ─ painel de locais ─  │         └──────────────┴───────────────────┘
│ Explorar Salvos Ajuda │
└───────────────────────┘
```

### Identidade

- Azul `#003F7A` e verde `#008137`, coerentes com a identidade já usada no projeto.
- Amarelo `#FFCC00` para seleção e orientação; laranja `#F39325` como apoio do módulo espacial.
- Superfícies claras, contraste legível e componentes com cantos arredondados, sem transformar todo conteúdo em cartões idênticos.
- Tipografia Source Sans 3 com fallback de sistema; fontes hospedadas pelo próprio app quando adicionadas ao bundle.
- Ícones consistentes em SVG, alvos de toque confortáveis e textos em português.
- A inspiração no Waze está no modelo de interação; o nome, conteúdo e identidade do aplicativo são FCTE Campus.

### Movimento

- Entrada coordenada de busca e painel, seleção de marcador e transições entre lista e detalhes.
- Painel inferior com posições recolhida, intermediária e expandida; botões acessíveis oferecem as mesmas mudanças sem exigir arraste.
- Transições interrompíveis: uma nova seleção substitui a anterior, sem filas de animações ou saltos de mapa.
- Feedback de favorito e de localização; estados de carregamento sem informações inventadas.
- Animações contínuas terão pausa quando necessárias e serão suspensas fora da tela ou com a página oculta. Respeitar `prefers-reduced-motion` também nos movimentos de câmera do mapa.
- O mapa continua utilizável com movimento reduzido; evitar parallax e efeitos que disputem atenção com a navegação.

## Dados e comportamento

O catálogo inicial será um snapshot público versionado, importado das evidências existentes. Um importador explícito preservará ID, coordenadas, nome original, fonte e situação. A aplicação não dependerá da existência de diretórios irmãos após o build.

O domínio representará coordenadas com latitude e longitude nomeadas. A conversão de GeoJSON/KML `[longitude, latitude]` ocorrerá no adaptador de importação, com validação de intervalos e IDs únicos.

Todos os 14 marcadores poderão ser vistos, inclusive os três fora dos chunks, com sua situação identificada. Não transformar `eligible` em aprovação humana. Não fundir entradas ao UAC, nem a Praça Solar à Praça da FCTE. Categoria só será atribuída quando o nome ou metadado a sustentar; laboratórios genéricos continuam sem identificação.

A busca será textual local, tolerante a acentos e caixa, limitada aos campos reais. Não será apresentada como busca semântica ou RAG. Os filtros refletirão os tipos efetivamente disponíveis, evitando categorias vazias ou atributos não coletados, como tomadas funcionando.

Favoritos guardarão somente IDs e versão do formato no armazenamento do dispositivo. Leitura inválida ou indisponibilidade do armazenamento não deve derrubar o aplicativo. Não persistir localização precisa, perguntas pessoais ou histórico de navegação nesta versão.

Selecionar um ponto exibirá sua ficha e reposicionará o mapa considerando o painel aberto. Ao fechar a ficha, o foco voltará ao controle ou item que a abriu. Escape e o botão voltar deverão fechar a camada superior antes de abandonar o aplicativo. Uma URL poderá identificar o local selecionado por ID, sem coordenadas do usuário.

O controle de localização tratará permissão negada, timeout, indisponibilidade e precisão baixa. A posição ficará somente na memória da sessão. A primeira versão usará uma solicitação pontual; não ativará rastreamento contínuo ou serviço de localização em segundo plano.

Uma ação **Abrir no mapa externo** poderá levar ao destino público selecionado, com rótulo claro de abertura de outro serviço. Não enviar a localização do estudante nessa URL. O app não desenhará uma linha entre pontos nem exibirá tempo de caminhada como se fosse uma rota validada.

## Arquitetura

Organização proposta, a ser criada após aprovação:

```text
src/
├── app/                 composição, provedores, configuração e shell
├── campus/
│   ├── domain/          Local, Coordenada, Fonte e Situação
│   ├── application/     buscar, selecionar e consultar locais
│   ├── infrastructure/  catálogo público e conversão de dados
│   └── presentation/    mapa, filtros, lista e ficha
├── favorites/           casos de uso e persistência de IDs no dispositivo
├── knowledge/           contrato de pergunta, fontes e disponibilidade
│   ├── application/     porta do assistente e estados de consulta
│   ├── infrastructure/  adaptador indisponível e futuro cliente HTTP
│   └── presentation/    painel do assistente
├── installation/        instalação, atualização e conectividade do PWA
└── design/              tokens, ícones e componentes de interface
public/                  ícones e assets públicos
```

Dependências apontam para o domínio e os casos de uso. Entidades e busca não importam React, Leaflet ou armazenamento do navegador. Os adaptadores conhecem os contratos internos. A composição de implementações ocorre em `app`, sem contêiner de injeção ou abstrações vazias.

React cuidará de estado e componentes. Leaflet ficará encapsulado em um adaptador de mapa, criado uma vez e atualizado por dados; desmontagem deve liberar listeners, observadores e recursos. Não reconstruir o mapa a cada tecla da busca.

O estado compartilhado será limitado às funções que o usam. A escolha entre contexto e store pequena fica ao implementador conforme os consumidores reais; não criar um estado global para todo componente nem longas cadeias de props.

## PWA e conectividade

O app terá manifest com nome, ícones, cores, início e escopo corretos, além de modo standalone. O build de produção gerará o service worker; o desenvolvimento não deverá deixar um worker antigo interferir nas alterações.

O cache inicial cobrirá a estrutura do app, assets próprios e catálogo público empacotado. Com a primeira carga concluída, o estudante poderá abrir a estrutura e consultar a lista e favoritos sem conexão.

Os tiles públicos do OpenStreetMap não serão incluídos em precache, prefetch ou um pacote de mapa offline. A página seguirá o cache HTTP normal do provedor. Sem rede, mostrar aviso e manter lista e fichas acessíveis, sem prometer o mapa-base completo. Preservar atribuição e permitir trocar o provedor por configuração.

Respostas do RAG e requisições com informação pessoal não entrarão no cache público do service worker. Geolocalização e instalação serão tratadas conforme o suporte do navegador. A instalação será verificada em HTTPS ou localhost; os controles de instalação não devem afirmar que o iOS expõe o mesmo evento de instalação do Android.

Novas versões terão aviso de atualização com ação explícita de recarregar; não interromper uma consulta ou navegação por reload automático. O escopo do service worker será restrito ao aplicativo, sem controlar a documentação ou o coletor.

## Integração futura do RAG e do orquestrador

O frontend dependerá de uma porta do assistente, não do SDK do Gemini ou do Chroma. O domínio da consulta incluirá pergunta, campus, resposta, disponibilidade, fontes e motivo de ausência quando pertinente.

Na primeira versão, o adaptador informará indisponibilidade do assistente com uma mensagem útil e acesso à busca do mapa. Não gerar respostas enlatadas e apresentá-las como recuperação real; nenhum botão deverá simular um envio bem-sucedido ao RAG.

Quando o backend real existir, o cliente HTTP poderá enviar a pergunta a uma API versionada do módulo. O backend será responsável por autorização, recuperação, geração, chaves e validação de citações. A proposta de interface comum `POST /perguntar` será conciliada e versionada com o Grupo 04, não presumida como acordo já implementado.

O contrato deverá identificar o módulo `grupo09`, fontes e seus IDs, situação de resposta e contexto geográfico disponível. Localizações pessoais serão opcionais e usadas somente quando necessárias à pergunta. O orquestrador comum será um adaptador de entrada; não levará regras de RU ou disciplinas para o núcleo espacial.

## Critérios de aceite e verificação

- Os 14 IDs são preservados e aparecem no mapa e na lista; as limitações conhecidas continuam visíveis.
- Busca, filtro, seleção, limpar busca, favoritos e reenquadramento funcionam sem backend.
- Não há overflow horizontal a partir de 360 px; o layout respeita teclado virtual, áreas seguras e painéis expandidos.
- Busca e painéis podem ser usados por teclado, com rótulos, foco visível e alternativa a gestos de arraste.
- Movimento reduzido desliga deslocamentos não essenciais e pulsos contínuos.
- Falhas de tiles, GPS, armazenamento e rede produzem estados compreensíveis, mantendo as funções locais.
- O assistente apresenta sua indisponibilidade real e não atribui fontes a uma resposta não gerada.
- Manifest, ícones, escopo e service worker são conferidos no build de produção; abertura offline de estrutura e catálogo é verificada após uma carga online.
- Testes serão focados em comportamento: conversão de coordenadas, busca, filtros, favoritos e contrato/disponibilidade do assistente. Não criar testes que apenas reproduzam CSS ou estrutura de componentes.
- Executar verificação de tipos, build, testes pertinentes e conferência da interface em desktop e celular. Registrar limites de verificação caso o ambiente não permita uma captura visual real.

## Liberdade do implementador e limites

O implementador decidirá nomes de componentes, divisão de arquivos, espaçamentos finais, curvas e durações, biblioteca de ícones e versões compatíveis das dependências, fixadas no lockfile. Manter módulos proporcionais e arquivos legíveis, evitando diretórios genéricos de utilidades.

Não alterar dados ou código dos outros projetos para implementar esta versão. Não criar contas, publicar site, mudar configuração global de skills ou instalar ferramentas de vídeo como parte deste trabalho. O projeto deverá ter Git próprio antes de qualquer commit; o Git antigo na raiz do workspace não será usado.

## Referências técnicas consultadas

- [Vite](https://vite.dev/guide/) e [Vite PWA](https://vite-pwa-org.netlify.app/guide/).
- [Leaflet 1.9.4](https://leafletjs.com/reference-1.9.4.html) e [política de tiles do OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/).
- [Motion e acessibilidade](https://motion.dev/docs/react-accessibility).
- [Instalação de PWAs](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable) e [operação offline](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation).

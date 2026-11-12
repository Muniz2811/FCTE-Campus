# FCTE Campus · instruções do projeto

## Etapa atual

A implementação do PWA está em `src/`, com React/TypeScript, Vite, Leaflet e Motion. O RAG foi incorporado em `backend/`, antes localizado em `../unb-gama-rag`. API na porta 8001, proxy Vite em `/api/rag`, E5/Chroma locais e geração Gemini no backend. Os comandos npm `dev:rag`, `rag:prepare`, `rag:index`, `rag:check` e `test:rag` executam o Python com o diretório correto. Consulte `README.md` para iniciar. Não inventar respostas ou fontes, não colocar chaves no navegador e não implementar o orquestrador comum como parte de ajustes de interface.

Este é o módulo espacial do Grupo 09, a parte laranja do diagrama, no repositório FCTE-Campus. Frontend e RAG compartilham este repositório, mantendo o contrato HTTP e suas responsabilidades separadas. `../coleta-fcte`, `../residencia-grupo-9` e `../residencia-grupo-4` permanecem projetos distintos. Consumir dados por contratos e exportações, preservando a procedência. Antes de comandos Git, conferir a raiz efetiva do repositório; não incluir este projeto no Git antigo de `Challenge3` por engano. Não versionar backend/.venv, backend/.cache, backend/data/index, originais privados nem arquivos .env.

## Uso das skills instaladas

As skills estão em `.agents/skills/`. Ler o `SKILL.md` pertinente e seus recursos necessários antes de aplicá-lo. A instalação disponibiliza instruções; não significa que todos os programas, MCPs ou dependências mencionados por elas estejam instalados ou autorizados a executar.

Carregar as skills por fase, conforme o escopo do pedido. Instruções do usuário e do ambiente prevalecem. Não executar simultaneamente metodologias concorrentes nem iniciar uma auditoria, entrevista extensa ou refatoração de outros projetos durante uma tarefa de instalação.

| Trabalho | Skills principais |
|---|---|
| Definir o produto e planejar | `brainstorming`, `writing-plans`, `domain-modeling` |
| Arquitetura do módulo | `software-architecture`, `architecture-patterns`, `codebase-design` |
| Evoluir arquitetura existente | `improve-codebase-architecture`, `legacy-modernizer` |
| Contrato com o orquestrador | `api-design-principles`; manter domínio independente do transporte HTTP |
| Construir a interface | `frontend-design`, `impeccable`, `ui-ux-pro-max` |
| React | [`vercel-react-best-practices`](.agents/skills/react-best-practices/SKILL.md), [`vercel-composition-patterns`](.agents/skills/composition-patterns/SKILL.md), [`vercel-react-view-transitions`](.agents/skills/react-view-transitions/SKILL.md) |
| Qualidade visual e acessibilidade | `web-design-guidelines`, `accessibility-scan`, `accessibility-inspect`, `accessibility-audit`, `accessibility-fix`, `accessibility-diff` |
| Tokens da identidade existente | `extract-design-system` quando houver um alvo definido |
| Ilustrações e demonstrações animadas | `stageshow`; usar componentes reais nas telas funcionais |
| Vídeos e apresentações exportáveis | Família `remotion-*` |
| Desenvolvimento e correções | `test-driven-development`, `systematic-debugging`, revisão e `verification-before-completion` |

As referências de mídia em `tooling/resources.json` não são skills. Instalar bibliotecas e ferramentas de execução somente na etapa que as utilizar. Preservar licenças, avisos e referências dos fornecedores.

## Direção de produto para a próxima etapa

- Interface inspirada no Waze: mapa como superfície principal, busca evidente, locais selecionáveis e painel de detalhes; bottom sheet no celular e painel lateral em telas maiores.
- Identidade UnB/FCTE, coerente com a documentação do Grupo 09: azul e verde como base, amarelo e laranja como apoios. Consolidar os tokens antes dos componentes.
- Animações expressivas que expliquem busca, seleção, transição de painéis e estados. Preservar desempenho no celular, teclado, foco, contraste e `prefers-reduced-motion`; dar controle sobre movimentos contínuos.
- Separar domínio, casos de uso e adaptadores. Nomes devem expressar o assunto do módulo; evitar depósitos genéricos de funções. Criar abstrações quando houver responsabilidade real e manter o código proporcional ao problema.
- O RAG local tem Chroma, busca e geração Gemini com citações validadas. A integração HTTP é do Grupo 09; transporte, rotas, ocupação atual e orquestrador comum continuam fora do implementado. Não confundir citações existentes com prova automática de fundamentação semântica.
- Fotografias e sugestões de IA não confirmam ocupação atual, funcionamento de equipamentos, acessibilidade de trajetos ou andar de um prédio.
- A integração com o orquestrador será um adaptador do módulo. O contrato comum será definido e versionado antes de ligar os grupos; não misturar regras de RU e disciplinas ao domínio espacial.
- Chaves ficam no backend. Não copiar `.env`, fotos privadas ou dados pessoais de outros projetos para exemplos, catálogos ou consultas a serviços externos.

## Verificação

`python scripts/verify_skills.py` confere a instalação e seus hashes. `tooling/skills.lock.json` registra origens, commits e arquivos instalados; `tooling/resources.json` preserva a correspondência com o pedido e as referências. Não modificar conteúdo de fornecedor para adaptar a identidade do produto.

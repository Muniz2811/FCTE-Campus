// Números medidos na rodada de conferência de 18/11/2026 (gemini-3.5-flash-lite, índice local 41 fontes/214 trechos).
// Origem: backend/avaliacao/resultados/tres-modos-conferencia-20261118T131530Z/execucoes.json (operacionais, finais)
// e julgamentos.json da mesma pasta (qualidade, PRÉ-AVALIAÇÃO não revisada e não versionada).
// O exemplo H05 vem da mesma rodada; os tempos por agente vêm do campo trace da resposta multiagente.
// Para outra rodada, atualize os números e a constante ROUND.
import type { Ratio } from './model';

export type RouteArm = 'llm' | 'rag' | 'multiagente';
export interface Stop { who: string; what: string; meta?: string; chips?: string[]; ai?: boolean }
export interface Lane {
  arm: RouteArm; name: string; calls: string; summary: string; stops: Stop[];
  answer: string; verdict: string; correct: boolean; median: string; tokens: string; completeness: Ratio;
}

const r = (numerador: number, denominador: number): Ratio => ({ numerador, denominador, valor: denominador ? numerador / denominador : null });

export const ROUND = {
  date: '18 nov. 2026', folder: 'backend/avaliacao/resultados/tres-modos-conferencia-20261118T131530Z',
  model: 'gemini-3.5-flash-lite', questions: 8, executions: 24, providerFailures: 9,
};

export const EXAMPLE = { id: 'H05', kind: 'premissa incorreta', question: 'O COSMOS fica na sala 101 do térreo, correto?',
  reference: 'Não. LDTEA, 2º andar, sala 304.' };

export const lanes: Lane[] = [
  { arm: 'llm', name: 'Gemini isolado', calls: '1 chamada', summary: 'Responde de memória, sem consultar documentos do campus.',
    stops: [
      { who: 'Pergunta', what: 'Vai direto para o modelo, sem busca.' },
      { who: 'Gemini', what: 'Prompt livre: responder usando só o conhecimento do modelo.', meta: '12,3 s · 282 tokens', ai: true },
      { who: 'Resposta', what: 'Sem trechos para citar; no máximo uma URL genérica.' },
    ],
    answer: 'Não possuo a informação confirmada sobre a localização exata da sala do COSMOS no campus Gama/FCTE da UnB.',
    verdict: 'Absteve-se e não corrigiu a premissa', correct: false, median: '10,7 s', tokens: '2.502', completeness: r(1, 6) },
  { arm: 'rag', name: 'RAG atual', calls: '1 chamada', summary: 'Busca nos documentos curados e pede uma única resposta citada.',
    stops: [
      { who: 'Pergunta', what: 'Usada como está na consulta.' },
      { who: 'Busca híbrida', what: 'E5 (vetorial, Chroma) + BM25 (palavras), unidas por RRF.' },
      { who: 'Reranker', what: 'Cross-encoder reordena até 30 candidatos.', chips: ['c_df45 · DOC-018', 'c_f2c6 · DOC-005', '+2'] },
      { who: 'Gemini', what: 'Escreve afirmações, cada uma com os chunk_ids que a sustentam.', meta: '3.340 tokens', ai: true },
      { who: 'Validação', what: 'O backend recusa chunk_id que não foi recuperado.' },
    ],
    answer: 'Incorreto. O COSMOS localiza-se no Prédio LDTEA, no 2º andar, sala 304. [1]',
    verdict: 'Corrigiu a premissa · 27,1 s nesta execução', correct: true, median: '9,3 s', tokens: '18.743', completeness: r(5, 6) },
  { arm: 'multiagente', name: 'RAG multiagente', calls: '3 a 5 chamadas', summary: 'Três papéis do mesmo Gemini, com instruções diferentes, em sequência.',
    stops: [
      { who: 'Pergunta', what: 'Recebe o assunto da conversa anterior, quando houver.' },
      { who: 'Pesquisador · planeja', what: 'Quebra a pergunta em subconsultas.', chips: ['COSMOS FCTE UnB sala', 'laboratorio COSMOS FCTE localizacao'], meta: '10,8 s · 216 tokens', ai: true },
      { who: 'Pesquisador · busca', what: 'Busca híbrida + reranker por subconsulta; junta até 5 trechos, máx. 2 por documento.', meta: '1,9 s + 3,0 s' },
      { who: 'Redator', what: 'Escreve as afirmações com chunk_ids, só a partir dos trechos.', meta: '6,2 s · 1.618 tokens', ai: true },
      { who: 'Validação', what: 'Mesma checagem de chunk_ids do RAG atual.' },
      { who: 'Revisor', what: 'Confere cobertura e suporte. Decidiu aprovar.', meta: '1,7 s · 2.031 tokens', ai: true },
    ],
    answer: 'A premissa está incorreta, pois o laboratório COSMOS fica localizado no Prédio LDTEA, no 2 andar, na sala 304. [1]',
    verdict: 'Corrigiu a premissa · 23,7 s · 3.865 tokens', correct: true, median: '16,3 s', tokens: '34.054', completeness: r(5, 6) },
];

export const operational: { label: string; values: Record<RouteArm, string> }[] = [
  { label: 'Latência mediana', values: { llm: '10,7 s', rag: '9,3 s', multiagente: '16,3 s' } },
  { label: 'Tokens nas 8 respostas', values: { llm: '2.502', rag: '18.743', multiagente: '34.054' } },
  { label: 'Chamadas ao Gemini', values: { llm: '8', rag: '7', multiagente: '24' } },
  { label: 'Rodadas de correção', values: { llm: '—', rag: '—', multiagente: '0' } },
  { label: 'Sucesso na 1ª tentativa', values: { llm: '5/8', rag: '6/8', multiagente: '6/8' } },
];

// PRÉ-AVALIAÇÃO não revisada por pessoa.
export const quality: { label: string; values: Record<RouteArm, Ratio> }[] = [
  { label: 'Respostas completas', values: { llm: r(1, 6), rag: r(5, 6), multiagente: r(5, 6) } },
  { label: 'Correção de premissas falsas', values: { llm: r(0, 2), rag: r(2, 2), multiagente: r(2, 2) } },
  { label: 'Reconhecimento de ausência', values: { llm: r(2, 2), rag: r(2, 2), multiagente: r(2, 2) } },
];

// Conjunto coloquial (FAVORECE O MULTIAGENTE): backend/avaliacao/resultados/tres-modos-coloquial-20261118T150540Z.
// Resultado por modo: 'ok' respondeu certo, 'partial' certo mas incompleto, 'none' não encontrou, 'wrong' afirmou algo errado, 'fail' falha do provedor.
export type Outcome = 'ok' | 'partial' | 'none' | 'wrong' | 'fail';
export const COLLOQUIAL = { folder: 'backend/avaliacao/resultados/tres-modos-coloquial-20261118T150540Z',
  medians: { llm: '8,5 s', rag: '9,4 s', multiagente: '30,9 s' } as Record<RouteArm, string>,
  tokens: { llm: '2.579', rag: '10.503', multiagente: '36.931' } as Record<RouteArm, string> };
export const colloquial: { id: string; question: string; outcomes: Record<RouteArm, Outcome>; note: string }[] = [
  { id: 'C01', question: 'Tem quadra de futebol na unb do gama?', outcomes: { llm: 'wrong', rag: 'none', multiagente: 'none' }, note: 'O multiagente acertou numa sessão ao vivo, mas não nesta rodada.' },
  { id: 'C02', question: 'Onde eu vou se passar mal no campus?', outcomes: { llm: 'wrong', rag: 'none', multiagente: 'ok' }, note: 'Multiagente achou o Navs da DASU na FCTE.' },
  { id: 'C03', question: 'Tô muito ansioso com as provas, tem alguém pra conversar?', outcomes: { llm: 'wrong', rag: 'none', multiagente: 'ok' }, note: 'Multiagente achou SOU e DASU; o Gemini inventou serviços.' },
  { id: 'C04', question: 'Como eu pego ônibus pra chegar no campus do Gama?', outcomes: { llm: 'fail', rag: 'none', multiagente: 'none' }, note: 'Nenhum achou o DF no Ponto.' },
  { id: 'C05', question: 'A cadeira da minha sala não serve pra mim, o que eu faço?', outcomes: { llm: 'wrong', rag: 'none', multiagente: 'none' }, note: 'Nenhum achou o apoio da DACES.' },
  { id: 'C06', question: 'Quantos livros posso pegar de uma vez na biblioteca?', outcomes: { llm: 'none', rag: 'none', multiagente: 'none' }, note: 'Multiagente recuperou o documento certo e mesmo assim se absteve.' },
  { id: 'C07', question: 'Onde fica a biblioteca e como acesso artigos da CAPES de casa?', outcomes: { llm: 'partial', rag: 'wrong', multiagente: 'partial' }, note: 'RAG deu a Biblioteca Central; multiagente acertou a CAPES.' },
  { id: 'C08', question: 'Tem wifi no campus? Como eu conecto o celular? (controle)', outcomes: { llm: 'partial', rag: 'ok', multiagente: 'ok' }, note: 'Controle: o multiagente não piorou.' },
];

export const testSteps = [
  { value: '90', title: 'Testes unitários', text: 'Gemini simulado, sem custo. Os 6 testes novos falham no código original e passam no corrigido.', done: true },
  { value: '6', title: 'Cenários com Gemini real', text: 'Composta, premissa incorreta, sem resposta, Revisor pegando erro injetado e conversa com contexto.', done: true },
  { value: '48', title: 'Comparação dos 3 modos', text: '8 perguntas formais e 8 coloquiais em cada modo. As falhas técnicas foram do provedor e ficaram registradas.', done: true },
  { value: '48', title: 'Julgamento humano', text: 'Pré-avaliação feita contra o gabarito e os trechos. Falta uma pessoa conferir nos documentos originais.', done: false },
];

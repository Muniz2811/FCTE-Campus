import type { KnowledgeSource } from '../knowledge/application/assistant';

export type Arm = 'rag' | 'llm' | 'multiagente';
export type HistoricalArm = 'rag' | 'llm';
export interface Ratio { numerador: number; denominador: number; valor: number | null }
export interface Scores {
  tarefas: number; completude: Ratio; corroboracao: Ratio; ausencia: Ratio; premissas: Ratio;
  rastreabilidade: Ratio; hit_at_5?: Ratio; precisao_trechos?: Ratio; precisao_respondiveis?: Ratio;
  fundamentacao?: Ratio; adequacao_citacoes?: Ratio; mrr_at_5?: number;
  fatos_contraditos: number; fatos_nao_corroborados: number;
  latencia_valida_s: { media: number; mediana: number; p95: number };
  tentativas: number; falhas_tecnicas: number; sucesso_primeira_tentativa: Ratio; sucesso_por_tentativa: Ratio;
  soma_duracoes_tentativas_s: number; esforco_medio_tarefa_s: number;
  tokens_saidas_validas: Record<string, number>; saidas_validas_com_usage: number;
}
export interface GoldQuestion { id: string; pergunta: string; referencia: string; respondiveis: boolean;
  tipo: string; teste: string; evidencias: { source_id: string; trecho: string }[] }
export interface Evaluation {
  round: string; date: string; reviewer: string; model: string; baseVersion: string | null; currentBaseMatches: boolean | null;
  currentRetrievalMatches?: boolean | null; currentProfile?: string | null; currentMethod?: string | null;
  arms: Record<HistoricalArm, Scores> & Partial<Record<'multiagente', Scores>>; scenarios: Record<string, Record<HistoricalArm, Scores>>; questions: GoldQuestion[];
  goals: Record<string, number | string>; rubric: Record<string, string>;
  judgments: { qid: string; braco: Arm; completa: boolean; ausencia_correta?: boolean | null; observacao: string }[];
  persistence: { success: boolean; executedAt: string }; artifacts: { path: string; sha256: string }[];
}
export interface AgentStep {
  agent: string; action: string; status: string; durationMs: number;
  decision?: string; feedback?: string; errorType?: string;
}
export interface AgentSearch { query: string; chunkIds: string[]; reformulacao?: boolean }
export interface AgentUsage { agent: string; usage?: Record<string, number> | null; errorType?: string }
export interface LiveResponse {
  status: 'answered' | 'insufficient'; answer?: string; message?: string;
  claims: { text: string; sourceIds?: string[]; fontes?: string[] }[];
  sources?: KnowledgeSource[]; retrieved?: KnowledgeSource[]; requestId?: string; model?: string; baseVersion?: string;
  retrievalProfile?: string; retrievalMethod?: string;
  usage?: Record<string, number>; providerModelVersion?: string;
  trace?: AgentStep[]; searches?: AgentSearch[]; usageByAgent?: AgentUsage[];
  llmCalls?: number; correctionRounds?: number; multiagent?: boolean; decision?: string;
  usageCoverage?: { callsWithUsage: number; calls: number };
  drafts?: { round: number; response: { status: string; answer?: string; message?: string; claims: { text: string; sourceIds?: string[] }[] } }[];
}
export interface Attempt {
  id: string; arm: Arm; question: string; executedAt: string; model: string; baseVersion?: string;
  technicalStatus: number; elapsedSeconds: number | null; response?: LiveResponse; error?: string;
  generation?: Record<string, unknown>; promptSha256?: string;
  retrievalProfile?: string; retrievalMethod?: string; retrievalSignature?: string;
  traceability?: { resolved?: number | null; total?: number; value: number | null; reason: string };
}
export const percent = (value: number | null | undefined) => value == null ? 'N/A' :
  new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 2 }).format(value);
export const ratio = (value?: Ratio) => !value || value.valor === null ? 'N/A' :
  `${percent(value.valor)} · ${value.numerador}/${value.denominador}`;
export const safeUrl = (url: string) => { try { return ['http:', 'https:'].includes(new URL(url).protocol); } catch { return false; } };
export const fraction = (n: number, d: number) => d ? percent(n / d) : 'N/A';

export async function compare(arm: Arm, question: string, signal: AbortSignal): Promise<Attempt> {
  const start = performance.now();
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}api/v1/comparison/${arm}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: question, campus: 'gama' }), signal,
    });
    const data: unknown = await r.json();
    if (typeof data === 'object' && data !== null && 'technicalStatus' in data && 'id' in data && 'arm' in data && data.arm === arm) {
      const attempt = data as Attempt;
      if (attempt.technicalStatus !== 200 || (r.ok && ['answered', 'insufficient'].includes(attempt.response?.status ?? ''))) return attempt;
    }
    return { id: crypto.randomUUID(), arm, question, model: 'Não informado', executedAt: new Date().toISOString(),
      technicalStatus: r.status >= 400 ? r.status : 502, elapsedSeconds: (performance.now() - start) / 1000,
      error: 'O backend não devolveu uma comparação válida. Confira sua disponibilidade.' };
  } catch {
    // Não contar falha de rede como resposta válida, nem confundir tempo do navegador com tempo do servidor.
    return { id: crypto.randomUUID(), arm, question, model: 'Não informado', executedAt: new Date().toISOString(),
      technicalStatus: 0, elapsedSeconds: null, error: signal.aborted
        ? 'Espera encerrada no navegador. A chamada no servidor pode ainda consumir cota.' : 'Falha de conexão. Não há resultado disponível.' };
  }
}

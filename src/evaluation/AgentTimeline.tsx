import './agent-timeline.css';
import type { LiveResponse } from './model';

const pretty: Record<string, string> = {
  pesquisador: 'Pesquisador', redator: 'Redator', revisor: 'Revisor',
};
export function AgentTimeline({ response }: { response: LiveResponse }) {
  if (!response.trace?.length) return null;
  return <details className="agent-timeline" open>
    <summary>Etapas reais dos agentes · {response.llmCalls ?? 0} chamadas Gemini · {response.correctionRounds ?? 0} correção(ões)</summary>
    <ol aria-label="Linha do tempo da execução multiagente">
      {response.trace.map((step, i) => <li key={`${i}-${step.agent}-${step.action}`}>
        <div className="agent-step-heading"><strong>{pretty[step.agent] ?? step.agent}</strong>
          <span>{step.action.replaceAll('_', ' ')} · {(step.durationMs / 1000).toFixed(2)} s</span></div>
        <p><b>Estado:</b> {step.status === 'error' ? 'falha técnica' : step.status === 'skipped' ? 'etapa dispensada' : 'concluída'}
          {step.decision ? ` · Decisão: ${step.decision}` : ''}</p>
        {step.feedback && <p><b>Feedback:</b> {step.feedback}</p>}
      </li>)}
    </ol>
    {!!response.searches?.length && <details><summary>Subconsultas e evidências selecionadas</summary><ul>
      {response.searches.map((s, i) => <li key={i}>{s.query} · {s.chunkIds.length} trechos
        {s.reformulacao ? ' · reformulação' : ''}<small>{s.chunkIds.join(', ') || 'Nenhum trecho recuperado'}</small></li>)}
    </ul></details>}
    {response.drafts && response.drafts.length > 1 && <details><summary>Comparar rascunho e resposta corrigida</summary>
      {response.drafts.map(d => <section key={d.round} className="agent-draft"><h4>{d.round === 0 ? 'Antes da revisão' : 'Depois da correção'}</h4>
        <p>{d.response.answer || d.response.message || d.response.claims.map(c => c.text).join(' ')}</p></section>)}
    </details>}
    {response.usageByAgent?.length ? <details><summary>Consumo por agente</summary><ul>
      {response.usageByAgent.map((u, i) => <li key={i}>{pretty[u.agent] ?? u.agent}: {u.usage?.totalTokenCount ?? 'N/A'} tokens
        {u.errorType ? ` · Falha: ${u.errorType}` : ''}</li>)}
    </ul></details> : null}
    <p className="agent-timeline-note">Decisões são registradas a partir da execução do backend. A revisão automática não substitui a conferência humana das fontes.</p>
  </details>;
}

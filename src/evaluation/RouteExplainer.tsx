import type { ReactNode } from 'react';
import { motion } from 'motion/react';
import { EvaluationHeading } from './MetricsPanel';
import { ratio } from './model';
import { COLLOQUIAL, EXAMPLE, ROUND, colloquial, lanes, operational, quality, testSteps, type Outcome, type RouteArm } from './route-data';

const outcomeLabel: Record<Outcome, string> = { ok: 'Respondeu', partial: 'Parcial', none: 'Não encontrou', wrong: 'Errou', fail: 'Falha técnica' };
import '../design/route.css';

const armLabel: Record<RouteArm, string> = { llm: 'Gemini', rag: 'RAG', multiagente: 'Multiagente' };
const arms: RouteArm[] = ['llm', 'rag', 'multiagente'];

function Ours() {
  return <span className="route-ours">nosso ajuste</span>;
}

function Node({ title, text, kind, ours }: { title: string; text: string; kind?: 'agent' | 'check' | 'end'; ours?: boolean }) {
  return <div className={`route-node${kind ? ` ${kind}` : ''}`}><b>{title}{ours && <Ours />}</b><span>{text}</span></div>;
}

function Step({ title, text, kind, ours, exit }: { title: string; text: string; kind?: 'agent' | 'check' | 'end'; ours?: boolean; exit?: ReactNode }) {
  return <><div className="route-step"><Node title={title} text={text} kind={kind} ours={ours} />{exit ? <p className="route-exit">{exit}</p> : <span />}</div><span className="route-down" aria-hidden="true" /></>;
}

function QualityBars({ label, values }: (typeof quality)[number]) {
  return <div className="score-bars"><h3>{label}</h3>{arms.map(arm =>
    <div key={arm} className={`bar-row ${arm}`}><span>{armLabel[arm]}</span><div className="bar-track">
      <motion.div initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: .65 }} style={{ width: `${(values[arm].valor ?? 0) * 100}%` }} />
    </div><strong>{ratio(values[arm])}</strong></div>)}</div>;
}

export function RouteExplainer() {
  return <div className="evaluation-page route-page" id="route-panel" tabIndex={-1}>
    <EvaluationHeading title="Uma pergunta, três caminhos." description="Como a mesma pergunta atravessa o Gemini isolado, o RAG atual e o RAG multiagente, com tempos e tokens medidos em execução real." />

    <div className="report-context"><p><b>Rodada de {ROUND.date}</b> · {ROUND.questions} perguntas novas · {ROUND.executions} execuções<br />{ROUND.model} nos três modos · índice local com 41 fontes e 214 trechos</p></div>

    <div className="route-question"><span>{EXAMPLE.id} · {EXAMPLE.kind}</span><strong>“{EXAMPLE.question}”</strong><small>Gabarito: {EXAMPLE.reference}</small></div>

    <section className="report-section"><h2>O caminho em cada modo.</h2>
      <p>Pontos cheios são chamadas ao Gemini; pontos vazados são etapas locais, sem IA. Tempos de uma única execução variam com a carga do provedor; para comparar, use as medianas.</p>
      <div className="route-lanes">{lanes.map(lane => <article key={lane.arm} className={`route-lane ${lane.arm}`}>
        <header><h3>{lane.name}</h3><span className="route-calls">{lane.calls}</span><p>{lane.summary}</p></header>
        <ol className="route-stops">{lane.stops.map(stop => <li key={stop.who} className={stop.ai ? 'ai' : undefined}>
          <b>{stop.who}</b><span>{stop.what}</span>
          {stop.chips && <span className="route-chips">{stop.chips.map(c => <code key={c}>{c}</code>)}</span>}
          {stop.meta && <small>{stop.meta}</small>}
        </li>)}</ol>
        <blockquote>{lane.answer}<small className={lane.correct ? 'ok' : 'bad'}>{lane.verdict}</small></blockquote>
        <dl><dt>Mediana</dt><dd>{lane.median}</dd><dt>Tokens</dt><dd>{lane.tokens}</dd><dt>Completas *</dt><dd>{ratio(lane.completeness)}</dd></dl>
      </article>)}</div>
    </section>

    <section className="report-section"><h2>Dentro do multiagente.</h2>
      <p>Todos os desvios possíveis, como o código funciona hoje. As etiquetas <Ours /> marcam o que mudamos em cima do PR #5.</p>
      <ul className="route-limits" aria-label="Limites por pergunta">
        <li><b>3</b>buscas</li><li><b>5</b>chamadas ao Gemini</li><li><b>240 s</b>tempo total</li><li><b>5</b>trechos, máx. 2 por documento</li><li><b>1</b>rodada de correção</li>
      </ul>
      <div className="route-flow">
        <Step title="Pedido chega na API" text="POST /api/v1/multiagent ou /api/v1/comparison/multiagente" exit={<><b>401</b> no deploy sem token, só em /api/v1/multiagent <Ours /></>} />
        <Step title="Vaga livre?" kind="check" ours text="Uma consulta por vez. A vaga é sempre devolvida, mesmo se algo falhar no meio." exit={<><b>429</b> “Já há uma consulta em andamento”</>} />
        <div className="route-group"><span className="route-group-label">Pesquisador</span>
          <Step title="Contexto da conversa" text="Com previousRequestId, junta o assunto da pergunta anterior: “lá” vira “biblioteca”." />
          <Step title="Gemini planeja" kind="agent" text="1 a 3 subconsultas e uma reformulação de reserva." exit={<><b>503</b> se o Gemini estiver sobrecarregado, com a etapa no texto <Ours /></>} />
          <Step title="Busca por subconsulta" text="E5 + BM25 → RRF → Chroma → reranker. Se nada vier, tenta a reformulação." />
          <div className="route-step"><Node title="Há trechos?" kind="check" text="Junta as buscas intercaladas para não perder a segunda parte de perguntas compostas." /><p className="route-exit"><b>Abstenção</b> direta, sem chamar o Redator</p></div>
        </div>
        <span className="route-down" aria-hidden="true" />
        <div className="route-group"><span className="route-group-label">Redator</span>
          <Step title="Gemini escreve" kind="agent" text="Afirmações com chunk_ids, ou “insuficiente” com a lacuna explicada." exit={<>Se ele mesmo se abstiver, a explicação dele é mantida <Ours /></>} />
          <div className="route-step"><Node title="Citações conferidas" kind="check" text="Todo chunk_id citado precisa estar entre os trechos recuperados." /><p className="route-exit"><b>Falha técnica</b>: citação inventada é bloqueada</p></div>
        </div>
        <span className="route-down" aria-hidden="true" />
        <div className="route-group"><span className="route-group-label">Revisor</span>
          <Step title="Gemini revisa" kind="agent" text="Cobertura da pergunta e suporte de cada afirmação nos trechos citados." />
          <div className="route-outcomes">
            <p className="ok"><b>aprovar</b>Resposta segue com as fontes.</p>
            <p className="fix"><b>corrigir (1ª vez)</b>Redator refaz com o feedback e as claims_problematicas <Ours />. O feedback não vale como evidência <Ours />.</p>
            <p className="no"><b>insuficiente</b>Abstenção.</p>
          </div>
          <span className="route-down" aria-hidden="true" />
          <div className="route-step"><Node title="Revisão da correção" text="Só acontece depois de um “corrigir”." /><span /></div>
          <span className="route-down" aria-hidden="true" />
          <div className="route-outcomes">
            <p className="ok"><b>aprovar</b>Resposta corrigida segue.</p>
            <p className="no"><b>corrigir de novo</b>Abstenção com decisão nao_aprovado_apos_correcao <Ours /></p>
            <p className="no"><b>insuficiente</b>Abstenção.</p>
          </div>
        </div>
        <span className="route-down" aria-hidden="true" />
        <div className="route-step"><Node title="Log de auditoria e vaga devolvida" kind="end" ours text="Grava plano, buscas, rascunhos, pareceres e tokens por agente. Se o disco falhar, a resposta sai assim mesmo, marcada auditLogSaved: false." /><span /></div>
      </div>
    </section>

    <section className="report-section"><h2>Como testamos.</h2>
      <ol className="route-tests">{testSteps.map(step => <li key={step.title}><strong>{step.value}</strong><h3>{step.title}</h3><p>{step.text}</p><small className={step.done ? 'ok' : 'pending'}>{step.done ? 'Concluído' : 'Pendente'}</small></li>)}</ol>
    </section>

    <section className="report-section"><h2>O que a conferência mostrou.</h2>
      <p>Na amostra, RAG atual e multiagente empataram em qualidade; o multiagente levou cerca de 1,8× o tempo e 1,8× os tokens. O Revisor não precisou corrigir nenhuma resposta real: só corrigiu quando injetamos um erro de propósito.</p>
      <div className="route-table"><table><thead><tr><th>Medida (8 perguntas)</th>{arms.map(arm => <th key={arm} className={arm}>{armLabel[arm]}</th>)}</tr></thead>
        <tbody>{operational.map(row => <tr key={row.label}><td>{row.label}</td>{arms.map(arm => <td key={arm}>{row.values[arm]}</td>)}</tr>)}</tbody></table></div>
      <div className="quality-charts">{quality.map(q => <QualityBars key={q.label} {...q} />)}</div>
    </section>

    <section className="report-section"><h2>Quando a pessoa fala do seu jeito.</h2>
      <p>A pergunta “Tem quadra de futebol na unb do gama?” mostrou o ponto fraco do RAG atual: o documento diz “Quadra de esportes”, e a busca única não encontra. O Pesquisador do multiagente reescreve a busca com outras palavras. Testamos isso com 8 perguntas coloquiais.</p>
      <aside className="evaluation-notice"><strong>Este conjunto favorece o multiagente de propósito.</strong><p>As perguntas foram escolhidas depois de confirmar que a busca do RAG atual não encontra o documento certo (C01–C06) ou encontra só uma parte (C07). A C08 é controle. Ele testa uma hipótese e não mede o desempenho médio.</p></aside>
      <div className="route-table"><table><thead><tr><th>Pergunta</th>{arms.map(arm => <th key={arm} className={arm}>{armLabel[arm]}</th>)}</tr></thead>
        <tbody>{colloquial.map(row => <tr key={row.id}><td><b>{row.id}</b> {row.question}<small className="route-row-note">{row.note}</small></td>
          {arms.map(arm => <td key={arm}><span className={`route-outcome ${row.outcomes[arm]}`}>{outcomeLabel[row.outcomes[arm]]}</span></td>)}</tr>)}
          <tr><td>Latência mediana · tokens</td>{arms.map(arm => <td key={arm}>{COLLOQUIAL.medians[arm]} · {COLLOQUIAL.tokens[arm]}</td>)}</tr></tbody></table></div>
      <p>O multiagente respondeu C02 e C03 e acertou a parte da CAPES na C07, onde o RAG atual errou a biblioteca. Mas o ganho é instável: a quadra (C01) foi encontrada numa sessão ao vivo e não nesta rodada. Ele vem da reformulação das buscas, não do Revisor, e custou cerca de 3× o tempo e os tokens do RAG atual.</p>
    </section>

    <aside className="evaluation-notice"><strong>* Qualidade ainda não revisada por pessoa.</strong>
      <p>Completude, premissas e ausência vêm de uma pré-avaliação feita contra o gabarito e o texto dos trechos. Os números passam a valer depois que alguém do grupo conferir cada resposta nos documentos originais. Tempos, tokens e chamadas são medidas automáticas e já são finais.</p>
      <p>Origem: {ROUND.folder} e {COLLOQUIAL.folder}.</p>
    </aside>
  </div>;
}

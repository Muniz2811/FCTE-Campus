import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { ArrowUp, Download, LoaderCircle, RefreshCw, Square } from 'lucide-react';
import { ChatAnswer } from '../knowledge/presentation/ChatAnswer';
import { AgentTimeline } from './AgentTimeline';
import { compare, fraction, percent, safeUrl, type Arm, type Attempt, type Evaluation, type GoldQuestion, type Ratio } from './model';
import { downloadJson, EvaluationHeading } from './MetricsPanel';

interface Run { id: string; question: string; attempts: Record<Arm, Attempt[]> }
type Judgment = '' | 'yes' | 'no';
interface Fact { text: string; verdict: '' | 'corroborated' | 'contradicted' | 'unknown'; grounded: Judgment }
interface Review { reviewer: string; notes: string; answerable: Judgment; premise: Judgment; complete: Judgment;
  absence: Judgment; corrected: Judgment; relevant: Record<string, Judgment>; facts: Fact[]; links: Record<string, Judgment> }
const arms: Arm[] = ['llm', 'rag', 'multiagente'];
const armName = (arm: Arm) => arm === 'rag' ? 'RAG atual' : arm === 'multiagente' ? 'RAG multiagente' : 'Gemini isolado';
const chosen = (run: Run, arm: Arm) => run.attempts[arm].find(a => a.technicalStatus === 200);
const linkPairs = (attempt: Attempt) => (attempt.response?.claims ?? []).flatMap((c, i) => (c.sourceIds ?? []).map(id => ({ key: `${i}:${id}`, id, text: c.text })));
function makeReview(attempt: Attempt, gold?: GoldQuestion): Review {
  return { reviewer: '', notes: '', answerable: gold ? gold.respondiveis ? 'yes' : 'no' : '', premise: gold ? gold.tipo === 'premissa_incorreta' ? 'yes' : 'no' : '', complete: '', absence: '', corrected: '', relevant: {}, links: {},
    facts: (attempt.response?.claims ?? []).map(c => ({ text: c.text, verdict: '', grounded: '' })) };
}
function reviewMetrics(attempt: Attempt, review: Review) {
  const ready = Boolean(review.reviewer.trim() && review.notes.trim());
  const r = (n: number, d: number, done: boolean): Ratio | null => ready && done
    ? { numerador: n, denominador: d, valor: d ? n / d : null } : null;
  const factsDone = review.facts.every(f => f.text.trim() && f.verdict);
  const retrieved = attempt.response?.retrieved ?? [], pairs = linkPairs(attempt);
  const relevantDone = retrieved.every(t => review.relevant[t.id]);
  const relevant = retrieved.filter(t => review.relevant[t.id] === 'yes').length;
  const first = retrieved.findIndex(t => review.relevant[t.id] === 'yes');
  return {
    identified: ready,
    completude: r(Number(review.complete === 'yes'), 1, review.answerable === 'yes' && !!review.complete),
    corroboracao: r(review.facts.filter(f => f.verdict === 'corroborated').length, review.facts.length, factsDone),
    fatos_contraditos: ready && factsDone ? review.facts.filter(f => f.verdict === 'contradicted').length : null,
    fatos_nao_corroborados: ready && factsDone ? review.facts.filter(f => f.verdict === 'unknown').length : null,
    ausencia: r(Number(review.absence === 'yes'), 1, review.answerable === 'no' && !!review.absence),
    premissas: r(Number(review.corrected === 'yes'), 1, review.premise === 'yes' && !!review.corrected),
    hit_at_5: attempt.arm !== 'llm' ? r(Number(relevant > 0), 1, review.answerable === 'yes' && relevantDone) : null,
    precisao_trechos: attempt.arm !== 'llm' ? r(relevant, retrieved.length, relevantDone) : null,
    precisao_respondiveis: attempt.arm !== 'llm' ? r(relevant, retrieved.length, review.answerable === 'yes' && relevantDone) : null,
    mrr_at_5: ready && attempt.arm !== 'llm' && relevantDone && review.answerable === 'yes' ? first < 0 ? 0 : 1 / (first + 1) : null,
    fundamentacao: attempt.arm !== 'llm' ? r(review.facts.filter(f => f.grounded === 'yes').length, review.facts.length,
      review.facts.every(f => f.text.trim() && f.grounded)) : null,
    adequacao_citacoes: attempt.arm !== 'llm' ? r(pairs.filter(p => review.links[p.key] === 'yes').length, pairs.length,
      pairs.every(p => review.links[p.key])) : null,
  };
}
function JudgeSelect({ label, value, onChange }: { label: string; value: Judgment; onChange(value: Judgment): void }) {
  return <label className="judge-select">{label}<select value={value} onChange={e => onChange(e.target.value as Judgment)}><option value="">Não avaliado</option><option value="yes">Sim</option><option value="no">Não</option></select></label>;
}
function ReviewPanel({ attempt, gold, review, update }: { attempt: Attempt; gold?: GoldQuestion; review: Review; update(value: Review): void }) {
  const retrieved = attempt.response?.retrieved ?? [], pairs = linkPairs(attempt);
  const patch = (value: Partial<Review>) => update({ ...review, ...value });
  const factsDone = review.facts.every(f => f.verdict !== '');
  const groundDone = review.facts.every(f => f.grounded !== '');
  const relevantDone = retrieved.every(t => review.relevant[t.id]);
  const nRelevant = retrieved.filter(t => review.relevant[t.id] === 'yes').length;
  const first = retrieved.findIndex(t => review.relevant[t.id] === 'yes');
  const linksDone = pairs.every(p => review.links[p.key]);
  return <details className="live-review"><summary>Revisar qualidade · {armName(attempt.arm)}</summary><div className="review-content">
    <p>Preencha após conferir as evidências. Estes julgamentos são manuais e não alteram a resposta. Uma afirmação do modelo pode conter vários fatos: separe-os antes de pontuar.</p>
    {gold && <blockquote><b>Gabarito {gold.id}:</b> {gold.referencia}{gold.evidencias.map((e, i) => <p key={i}>{e.source_id}: {e.trecho}</p>)}</blockquote>}
    <label>Responsável pela revisão<input value={review.reviewer} onChange={e => patch({ reviewer: e.target.value })} placeholder="Seu nome" /></label>
    <div className="review-fields"><JudgeSelect label="A base permite responder?" value={review.answerable} onChange={answerable => patch({ answerable })} /><JudgeSelect label="Há uma premissa falsa?" value={review.premise} onChange={premise => patch({ premise })} />
      {review.answerable === 'yes' && <JudgeSelect label="Atendeu todos os atributos do gabarito?" value={review.complete} onChange={complete => patch({ complete })} />}
      {review.answerable === 'no' && <JudgeSelect label="Admitiu corretamente a ausência, sem inventar?" value={review.absence} onChange={absence => patch({ absence })} />}
      {review.premise === 'yes' && <JudgeSelect label="Corrigiu explicitamente a premissa?" value={review.corrected} onChange={corrected => patch({ corrected })} />}
    </div>
    {attempt.arm !== 'llm' && <fieldset><legend>1. Relevância dos trechos recuperados</legend>{retrieved.length === 0 && <p>Nenhum trecho retornado. Precisão N/A; Hit e recíproco do rank valem zero se a pergunta for respondível.</p>}{retrieved.map((t, i) => <div className="review-chunk" key={t.id}><details><summary>#{i + 1} · {t.title} · {t.id}</summary><p>{t.excerpt}</p></details><JudgeSelect label="Ajuda a responder exatamente à pergunta?" value={review.relevant[t.id] ?? ''} onChange={value => patch({ relevant: { ...review.relevant, [t.id]: value } })} /></div>)}</fieldset>}
    <fieldset><legend>{attempt.arm !== 'llm' ? '2.' : '1.'} Fatos atômicos</legend><p>Compare com documentos de referência, não com a resposta do outro sistema. Sem fatos produzidos, as razões factuais são N/A.</p>
      {review.facts.map((fact, i) => <div className="review-fact" key={i}><label>Fato {i + 1}<textarea value={fact.text} onChange={e => patch({ facts: review.facts.map((f, j) => j === i ? { ...f, text: e.target.value, verdict: '', grounded: '' } : f) })} /></label><label>Conferência nas referências<select value={fact.verdict} onChange={e => patch({ facts: review.facts.map((f, j) => j === i ? { ...f, verdict: e.target.value as Fact['verdict'] } : f) })}><option value="">Não avaliado</option><option value="corroborated">Corroborado</option><option value="contradicted">Contradito</option><option value="unknown">Não corroborado</option></select></label>
        {attempt.arm !== 'llm' && <JudgeSelect label="Sustentado pelos chunks citados?" value={fact.grounded} onChange={grounded => patch({ facts: review.facts.map((f, j) => i === j ? { ...f, grounded } : f) })} />}
        <button className="text-button" onClick={() => patch({ facts: review.facts.filter((_, j) => i !== j) })}>Remover este fato</button></div>)}
      <button className="text-button" onClick={() => patch({ facts: [...review.facts, { text: '', verdict: '', grounded: '' }] })}>+ Separar ou acrescentar um fato</button>
    </fieldset>
    {attempt.arm !== 'llm' && <fieldset><legend>3. Adequação de cada citação</legend>{pairs.map(pair => <div className="review-fact" key={pair.key}><p>{pair.text}<br /><code>{pair.id}</code></p><JudgeSelect label="Esse chunk sustenta essa afirmação?" value={review.links[pair.key] ?? ''} onChange={v => patch({ links: { ...review.links, [pair.key]: v } })} /></div>)}{!pairs.length && <p>Sem vínculos citados: N/A.</p>}</fieldset>}
    <label>Justificativa e referências consultadas<textarea value={review.notes} onChange={e => patch({ notes: e.target.value })} placeholder="Registre evidências, divergências e a divisão de fatos utilizada." /></label>
    <div className="manual-scores" aria-live="polite"><h3>Resultado da revisão desta pergunta</h3><p>{review.reviewer.trim() && review.notes.trim() ? 'Revisão identificada. Valores parciais até todos os campos aplicáveis serem preenchidos.' : 'Rascunho: identifique o revisor e registre as evidências antes de usar estes resultados.'}</p>
      <dl><dt>Completude</dt><dd>{review.answerable === 'yes' && review.complete ? fraction(Number(review.complete === 'yes'), 1) : 'N/A · sem julgamento aplicável'}</dd>
        <dt>Corroboração factual</dt><dd>{factsDone ? `${fraction(review.facts.filter(f => f.verdict === 'corroborated').length, review.facts.length)} · ${review.facts.filter(f => f.verdict === 'corroborated').length}/${review.facts.length}` : 'Pendente'}</dd>
        <dt>Fatos contraditos / não corroborados</dt><dd>{factsDone ? `${review.facts.filter(f => f.verdict === 'contradicted').length} / ${review.facts.filter(f => f.verdict === 'unknown').length}` : 'Pendente'}</dd>
        <dt>Ausência reconhecida</dt><dd>{review.answerable === 'no' && review.absence ? fraction(Number(review.absence === 'yes'), 1) : 'N/A'}</dd>
        <dt>Premissa corrigida</dt><dd>{review.premise === 'yes' && review.corrected ? fraction(Number(review.corrected === 'yes'), 1) : 'N/A'}</dd>
        {attempt.arm !== 'llm' && <><dt>Hit@5 / recíproco do rank</dt><dd>{review.answerable === 'yes' && relevantDone ? `${fraction(Number(nRelevant > 0), 1)} / ${first < 0 ? '0' : (1 / (first + 1)).toFixed(4)}` : 'Pendente ou N/A'}</dd><dt>Precisão dos trechos</dt><dd>{relevantDone ? `${nRelevant}/${retrieved.length} · ${fraction(nRelevant, retrieved.length)}` : 'Pendente'}</dd><dt>Precisão nas respondíveis</dt><dd>{review.answerable === 'yes' && relevantDone ? fraction(nRelevant, retrieved.length) : 'N/A'}</dd><dt>Fundamentação factual</dt><dd>{groundDone ? fraction(review.facts.filter(f => f.grounded === 'yes').length, review.facts.length) : 'Pendente'}</dd><dt>Adequação das citações</dt><dd>{linksDone ? fraction(pairs.filter(p => review.links[p.key] === 'yes').length, pairs.length) : 'Pendente'}</dd></>}
      </dl><p>Rastreabilidade é conferida pelo backend e aparece junto da resposta. Persistência não é reavaliada por uma consulta ao servidor já aberto. Recuperação e fundamentação no contexto são N/A para o Gemini isolado.</p></div>
  </div></details>;
}

function Answer({ arm, attempts, pending, retry }: { arm: Arm; attempts: Attempt[]; pending: boolean; retry(): void }) {
  const selected = attempts.find(a => a.technicalStatus === 200), last = attempts.at(-1), result = selected?.response;
  return <article className={`comparison-answer ${arm}`}><header><span className="arm-dot" /><h2>{armName(arm)}</h2><small>{arm === 'multiagente' ? 'Pesquisador → Redator → Revisor' : arm === 'rag' ? 'Com documentos recuperados' : 'Sem documentos, busca ou histórico'}</small></header>
    <div className="answer-content" aria-live="polite">{pending ? <p className="live-pending"><LoaderCircle className="chat-spinner" size={18} />{arm !== 'llm' ? 'Recuperando evidências e consultando o Gemini…' : 'Consultando o Gemini…'}</p> : result ? <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      {arm !== 'llm' ? <ChatAnswer result={result.status === 'answered' ? { ...result, status: 'answered', answer: result.answer ?? '', sources: result.sources ?? [] } : { ...result, status: 'insufficient', message: result.message ?? '' }} onRetry={retry} /> : <><p className="chat-answer-text">{result.status === 'answered' ? result.claims.map(c => c.text).join('\n\n') : result.message}</p>{result.claims.some(c => c.fontes?.length) && <details className="chat-references"><summary>URLs sugeridas pelo Gemini · sem versão preservada</summary><ul>{[...new Set(result.claims.flatMap(c => c.fontes ?? []))].map(url => <li key={url}>{safeUrl(url) ? <a href={url} target="_blank" rel="noreferrer">{url}</a> : 'URL inválida omitida'}</li>)}</ul></details>}</>}
    </motion.div> : last ? <div role="alert"><p>{last.error} {last.technicalStatus > 0 ? `(HTTP ${last.technicalStatus})` : ''}</p><button className="text-button" onClick={retry}><RefreshCw size={15} />Repetir falha técnica</button></div> : <p className="empty-comparison">A mesma pergunta chegará aos três sistemas. As respostas aparecerão aqui.</p>}
    {arm === 'multiagente' && result && <AgentTimeline response={result} />}
    {selected?.auditLogSaved === false && <p role="status">A resposta foi preservada, mas o servidor não conseguiu gravar o log. Exporte esta sessão para guardar a evidência.</p>}
    {selected && <div className="attempt-metrics"><dl><dt>Tempo no backend</dt><dd>{selected.elapsedSeconds?.toFixed(2) ?? 'N/A'} s</dd><dt>Tokens de entrada / saída / raciocínio</dt><dd>{result?.usage ? `${result.usage.promptTokenCount ?? 'N/A'} / ${result.usage.candidatesTokenCount ?? 'N/A'} / ${result.usage.thoughtsTokenCount ?? 'N/A'}` : 'N/A · provedor não informou'}</dd><dt>Tokens totais informados</dt><dd>{result?.usage?.totalTokenCount ?? 'N/A'}</dd><dt>Rastreabilidade documental</dt><dd>{percent(selected.traceability?.value)}</dd></dl><p>{selected.traceability?.reason}</p><details><summary>Modelo e execução</summary><p>{selected.model}<br />{result?.providerModelVersion}<br />{selected.executedAt}<br />ID: {selected.id}<br />Base: {selected.baseVersion}</p></details></div>}
    {!!attempts.length && <details className="attempt-log"><summary>{attempts.length} tentativa(s) preservada(s)</summary><ol>{attempts.map(a => <li key={a.id}>{a.technicalStatus === 200 ? 'Saída válida' : a.technicalStatus ? `HTTP ${a.technicalStatus}` : 'Sem resposta HTTP'} · {a.elapsedSeconds?.toFixed(2) ?? 'N/A'} s</li>)}</ol></details>}
    </div>
  </article>;
}

export function LiveComparison({ data }: { data: Evaluation | null }) {
  const [question, setQuestion] = useState('Na biblioteca do Gama há lugar para estudar sozinho e em grupo?');
  const [runs, setRuns] = useState<Run[]>([]), [activeId, setActiveId] = useState('');
  const [pending, setPending] = useState<Partial<Record<Arm, boolean>>>({});
  const [working, setWorking] = useState(false);
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  const [error, setError] = useState('');
  const controllers = useRef<AbortController[]>([]), busyRef = useRef(false), stopRef = useRef(false);
  const active = runs.find(r => r.id === activeId), busy = working || Object.values(pending).some(Boolean);
  const gold = data?.questions.find(q => q.pergunta.trim().toLocaleLowerCase() === active?.question.trim().toLocaleLowerCase());
  useEffect(() => () => controllers.current.forEach(c => c.abort()), []);
  async function execute(run: Run, selectedArms: Arm[]) {
    if (busyRef.current) return;
    busyRef.current = true; stopRef.current = false; setWorking(true); setError('');
    for (const arm of selectedArms) {
      if (stopRef.current) break;
      const controller = new AbortController(); controllers.current.push(controller);
      const timeout = window.setTimeout(() => controller.abort(), arm === 'multiagente' ? 250_000 : 115_000);
      setPending(values => ({ ...values, [arm]: true }));
      try {
        const attempt = await compare(arm, run.question, controller.signal);
        setRuns(values => values.map(value => value.id === run.id ? { ...value, attempts: { ...value.attempts, [arm]: [...value.attempts[arm], attempt] } } : value));
      } finally {
        window.clearTimeout(timeout); controllers.current = controllers.current.filter(c => c !== controller);
        setPending(values => ({ ...values, [arm]: false }));
      }
    }
    busyRef.current = false; setWorking(false);
  }
  function start() {
    if (busyRef.current) return;
    if (!question.trim() || question.trim().length > 1200) { setError('Escreva uma pergunta de até 1.200 caracteres.'); return; }
    const run: Run = { id: crypto.randomUUID(), question: question.trim(), attempts: { rag: [], llm: [], multiagente: [] } };
    setRuns(values => [...values, run]); setActiveId(run.id); void execute(run, arms);
  }
  const getReview = (attempt: Attempt) => reviews[attempt.id] ?? makeReview(attempt, gold);
  return <div className="evaluation-page live-page" id="comparison-panel"><EvaluationHeading title="Pergunte uma vez. Compare lado a lado." description="Execução real de Gemini isolado, RAG atual e RAG multiagente. Nenhuma resposta é simulada." />
    <form className="comparison-form" onSubmit={e => { e.preventDefault(); start(); }}>
      {data && <label>Experimentar uma pergunta do relatório<select value="" disabled={busy} onChange={e => { const q = data.questions.find(q => q.id === e.target.value); if (q) setQuestion(q.pergunta); }}><option value="">Escolha uma das 15 perguntas…</option>{data.questions.map(q => <option key={q.id} value={q.id}>{q.id} · {q.pergunta}</option>)}</select></label>}
      <label htmlFor="comparison-question">Sua pergunta para os três sistemas<textarea id="comparison-question" rows={3} maxLength={1200} value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} /></label>
      <div className="comparison-form-footer"><p>A comparação pode consumir várias chamadas Gemini, especialmente no multiagente. Consome a cota configurada no backend. O RAG pode se abster sem chamar a API quando não houver trechos.</p>{busy ? <button type="button" className="primary-button" onClick={() => { stopRef.current = true; controllers.current.forEach(c => c.abort()); }}><Square size={15} />Parar espera</button> : <button className="primary-button" type="submit"><ArrowUp size={17} />Comparar respostas</button>}</div>{error && <p role="alert">{error}</p>}
    </form>
    {!!runs.length && <><div className="comparison-run-controls"><label>Execuções desta sessão<select disabled={busy} value={activeId} onChange={e => setActiveId(e.target.value)}>{runs.map((r, i) => <option key={r.id} value={r.id}>#{i + 1} · {r.question}</option>)}</select></label><button className="text-button" disabled={busy} onClick={() => downloadJson({ exportedAt: new Date().toISOString(), methodology: 'RAG atual versus Gemini isolado versus multiagente; primeira saída válida; revisões manuais, sem juiz LLM. Tempos medidos no backend; sem retentativas automáticas.', historicalRound: data?.round, runs, reviews: Object.fromEntries(runs.flatMap(r => arms.flatMap(a => { const s = chosen(r, a); return s ? [[s.id, { judgments: reviews[s.id] ?? makeReview(s, data?.questions.find(q => q.pergunta === r.question)), metrics: reviewMetrics(s, reviews[s.id] ?? makeReview(s, data?.questions.find(q => q.pergunta === r.question))) }]] as const : []; }))) }, 'fcte-comparacao-sessao.json')}><Download size={16} />Exportar sessão e revisão</button></div>
      {active && <><p className="submitted-question"><b>Pergunta submetida:</b> {active.question}</p><div className="comparison-columns">{arms.map(arm => <Answer key={arm} arm={arm} attempts={active.attempts[arm]} pending={!!pending[arm]} retry={() => { if (!chosen(active, arm)) void execute(active, [arm]); }} />)}</div>
      <section className="report-section"><h2>Qual respondeu melhor?</h2><p>Tempo e consumo já estão medidos. Para avaliar a qualidade, confira os trechos e preencha a revisão abaixo. Os dados do gabarito nunca são enviados ao Gemini.</p>{arms.map(arm => { const a = chosen(active, arm); return a && <ReviewPanel key={a.id} attempt={a} gold={gold} review={getReview(a)} update={review => setReviews(values => ({ ...values, [a.id]: review }))} />; })}</section></>}
      <SessionMetrics runs={runs} />
      <QualityMetrics runs={runs} reviews={reviews} />
    </>}
    {!runs.length && <div className="live-empty"><div className="live-flow"><span>Sua pergunta</span><span>Gemini + dois RAGs</span><span>Três respostas</span><span>Métricas + revisão</span></div><p>A comparação começa quando você enviar. Nenhuma chamada é feita ao abrir esta aba.</p></div>}
  </div>;
}
function SessionMetrics({ runs }: { runs: Run[] }) {
  return <section className="report-section"><h2>Disponibilidade nesta sessão</h2><p>Valores agregados das tentativas concluídas. As três execuções são sequenciais para evitar conflito de semáforo; o tempo ao vivo não reproduz o ensaio histórico sequencial. Não há percentil confiável com poucas amostras.</p><div className="session-metrics">{arms.map(arm => {
    const attempted = runs.filter(r => r.attempts[arm].length), attempts = attempted.flatMap(r => r.attempts[arm]);
    const valid = attempted.flatMap(r => { const a = chosen(r, arm); return a ? [a] : []; });
    const durations = valid.flatMap(a => a.elapsedSeconds === null ? [] : [a.elapsedSeconds]);
    const sorted = [...durations].sort((a, b) => a - b);
    const median = sorted.length ? (sorted[Math.floor((sorted.length - 1) / 2)] + sorted[Math.ceil((sorted.length - 1) / 2)]) / 2 : null;
    const usage = valid.filter(a => a.response?.usage && Object.keys(a.response.usage).length);
    const totalSeconds = attempts.reduce((s, a) => s + (a.elapsedSeconds ?? 0), 0), timingComplete = attempts.every(a => a.elapsedSeconds !== null);
    return <article key={arm}><h3>{armName(arm)}</h3><dl><dt>Saídas válidas após retentativas</dt><dd>{valid.length}/{attempted.length} · {fraction(valid.length, attempted.length)}</dd><dt>Sucesso inicial</dt><dd>{fraction(attempted.filter(r => r.attempts[arm][0]?.technicalStatus === 200).length, attempted.length)}</dd><dt>Sucesso por tentativa</dt><dd>{fraction(attempts.filter(a => a.technicalStatus === 200).length, attempts.length)}</dd><dt>Falhas / tentativas</dt><dd>{attempts.filter(a => a.technicalStatus !== 200).length}/{attempts.length}</dd><dt>Latência média / mediana</dt><dd>{durations.length ? `${(durations.reduce((a, b) => a + b, 0) / durations.length).toFixed(2)} / ${median?.toFixed(2)} s` : 'N/A'}</dd><dt>P95 das saídas válidas</dt><dd>{sorted.length >= 2 ? (sorted[Math.floor((sorted.length - 1) * .95)] + (sorted[Math.ceil((sorted.length - 1) * .95)] - sorted[Math.floor((sorted.length - 1) * .95)]) * (((sorted.length - 1) * .95) % 1)).toFixed(2) + ' s · amostra pequena' : 'N/A · precisa ≥2 saídas'}</dd><dt>Esforço total / por execução</dt><dd>{timingComplete && attempted.length ? `${totalSeconds.toFixed(2)} / ${(totalSeconds / attempted.length).toFixed(2)} s` : 'N/A · tempo incompleto'}</dd><dt>Tokens totais das saídas válidas</dt><dd>{usage.length ? usage.reduce((s, a) => s + (a.response?.usage?.totalTokenCount ?? 0), 0).toLocaleString('pt-BR') : 'N/A'} · usage {usage.length}/{valid.length}</dd></dl></article>;
  })}</div><p>Esta sessão fica em memória até recarregar a página; exporte o JSON para preservar a revisão. As tentativas do servidor também são salvas em backend/data/execucoes. Não repetimos respostas erradas para escolher uma mais favorável.</p></section>;
}

function QualityMetrics({ runs, reviews }: { runs: Run[]; reviews: Record<string, Review> }) {
  const names = { completude: 'Completude', corroboracao: 'Corroboração factual', fundamentacao: 'Fundamentação factual',
    ausencia: 'Reconhecimento de ausência', premissas: 'Correção de premissas', hit_at_5: 'Hit@5',
    precisao_trechos: 'Precisão dos trechos', precisao_respondiveis: 'Precisão nas respondíveis', adequacao_citacoes: 'Adequação das citações' };
  return <section className="report-section"><h2>Qualidade das execuções revisadas</h2><p>Agregamos numeradores e denominadores, usando a primeira saída válida de cada execução. Entram somente julgamentos preenchidos, com revisor e justificativa. Ausência de revisão não vira nota zero. Amostras repetidas continuam identificadas como novas execuções.</p><div className="session-metrics">{arms.map(arm => {
    const valid = runs.flatMap(run => { const a = chosen(run, arm); return a ? [a] : []; });
    const scored = valid.flatMap(a => reviews[a.id] ? [reviewMetrics(a, reviews[a.id])] : []);
    const ranks = scored.flatMap(s => s.mrr_at_5 === null ? [] : [s.mrr_at_5]);
    const trace = valid.flatMap(a => a.traceability?.value != null && a.traceability.total != null && a.traceability.resolved != null ? [a.traceability] : []);
    return <article key={arm}><h3>{armName(arm)}</h3><p>{scored.filter(s => s.identified).length}/{valid.length} saídas com revisão identificada</p><dl>
      {Object.entries(names).map(([key, name]) => {
        const ratios = scored.flatMap(s => { const r = s[key as keyof typeof names]; return r && r.denominador ? [r] : []; });
        const n = ratios.reduce((sum, r) => sum + r.numerador, 0), d = ratios.reduce((sum, r) => sum + r.denominador, 0);
        return <div className="quality-metric-line" key={key}><dt>{name}</dt><dd>{d ? `${n}/${d} · ${fraction(n, d)}` : 'N/A / pendente'}<small>{ratios.length} execução(ões) aplicáveis e julgadas</small></dd></div>;
      })}
      <dt>MRR@5</dt><dd>{ranks.length ? (ranks.reduce((a, b) => a + b, 0) / ranks.length).toFixed(4) : 'N/A / pendente'}</dd>
      <dt>Fatos contraditos / não corroborados</dt><dd>{scored.some(s => s.fatos_contraditos !== null) ? `${scored.reduce((sum, s) => sum + (s.fatos_contraditos ?? 0), 0)} / ${scored.reduce((sum, s) => sum + (s.fatos_nao_corroborados ?? 0), 0)}` : 'Pendente'}</dd>
      <dt>Rastreabilidade documental</dt><dd>{fraction(trace.reduce((sum, t) => sum + (t.resolved ?? 0), 0), trace.reduce((sum, t) => sum + (t.total ?? 0), 0))}</dd>
      <dt>Persistência</dt><dd>N/A · não reavaliada</dd>
    </dl></article>;
  })}</div></section>;
}

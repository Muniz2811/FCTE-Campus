import { useState } from 'react';
import { motion } from 'motion/react';
import { ArrowRight, Check, Download, RefreshCw } from 'lucide-react';
import { metrics } from './metrics';
import { percent, ratio, type Evaluation, type Ratio, type Scores } from './model';

export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}
export function EvaluationHeading({ title, description }: { title: string; description: string }) {
  return <header className="evaluation-heading"><span className="evaluation-brand">FCTE Campus / Laboratório</span><h1>{title}</h1><p>{description}</p></header>;
}
function Bars({ label, rag, llm }: { label: string; rag: Ratio; llm: Ratio }) {
  return <div className="score-bars"><h3>{label}</h3>{([['rag', rag], ['llm', llm]] as const).map(([arm, score]) =>
    <div key={arm} className={`bar-row ${arm}`}><span>{arm === 'rag' ? 'RAG' : 'Gemini'}</span><div className="bar-track">
      <motion.div initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: .65 }} style={{ width: `${(score.valor ?? 0) * 100}%` }} />
    </div><strong>{ratio(score)}</strong></div>)}</div>;
}
function ChunkExample() {
  const [relevant, setRelevant] = useState([false, true, false, false, false]);
  const count = relevant.filter(Boolean).length, first = relevant.findIndex(Boolean);
  return <section className="chunk-example"><div><h2>Encontrar uma pista ≠ aproveitar todas.</h2><p>Exemplo ilustrativo: marque os trechos úteis para uma única pergunta respondível. Veja como as métricas mudam.</p></div>
    <div className="example-chunks">{relevant.map((value, index) => <button key={index} aria-pressed={value} onClick={() => setRelevant(values => values.map((v, i) => i === index ? !v : v))}>
      <span>Trecho {index + 1}</span><span>{value ? <Check size={22} /> : '—'}</span><small>{value ? 'Relevante' : 'Não relevante'}</small></button>)}</div>
    <div className="example-results" aria-live="polite"><span>Hit@5 <b>{count ? '1/1 = 100%' : '0/1 = 0%'}</b></span><span>Precisão <b>{count}/5 = {percent(count / 5)}</b></span><span>Recíproco do rank <b>{first < 0 ? '0' : `1/${first + 1} = ${(1 / (first + 1)).toFixed(2)}`}</b></span></div>
  </section>;
}
function valueFor(scores: Scores, key: string, data: Evaluation): string {
  const value = scores[key as keyof Scores];
  if (value && typeof value === 'object' && 'valor' in value) return ratio(value as Ratio);
  if (key === 'mrr_at_5') return scores.mrr_at_5?.toFixed(4) ?? 'N/A';
  if (key === 'latencia') return `${scores.latencia_valida_s.media.toFixed(2)} s média · ${scores.latencia_valida_s.mediana.toFixed(2)} s mediana · ${scores.latencia_valida_s.p95.toFixed(2)} s P95`;
  if (key === 'esforco') return `${scores.esforco_medio_tarefa_s.toFixed(2)} s/tarefa · ${scores.soma_duracoes_tentativas_s.toFixed(2)} s total`;
  if (key === 'tokens') return `${scores.tokens_saidas_validas.totalTokenCount.toLocaleString('pt-BR')} tokens · usage em ${scores.saidas_validas_com_usage}/${scores.tarefas} saídas`;
  if (key === 'validas') return `${scores.tarefas}/15 = 100% após retentativas`;
  if (key === 'persistencia') return scores.hit_at_5 ? `${data.persistence.success ? '1 · sucesso' : '0 · falha'}` : 'N/A';
  return typeof value === 'number' ? String(value) : 'N/A';
}
export function MetricsPanel({ data, error, reload }: { data: Evaluation | null; error: string; reload(): void }) {
  return <div className="evaluation-page" id="metrics-panel" tabIndex={-1}><EvaluationHeading title="Evidências, não impressões." description="O que medimos ao comparar nosso RAG com o mesmo Gemini sem consultar a base do campus." />
    {!data ? <p className="evaluation-notice" role="status">{error || 'Carregando os resultados registrados…'}{error && <button onClick={reload} className="text-button"><RefreshCw size={16} />Tentar novamente</button>}</p> : <>
      <div className="report-context"><p><b>Rodada de 12 nov. 2026</b> · 15 perguntas · 4 cenários<br />{data.model} nos dois sistemas · mesma temperatura e limite de saída</p><button className="text-button" onClick={() => downloadJson(data, `${data.round}-painel.json`)}><Download size={16} />Exportar resultados</button></div>
      {data.currentRetrievalMatches === false && <aside className="evaluation-notice"><strong>O perfil atual não foi avaliado nesta rodada.</strong><p>O servidor usa {data.currentProfile} · {data.currentMethod}. Os números abaixo pertencem à busca híbrida com reranker da rodada histórica; não comprovam a qualidade do perfil atual.</p></aside>}
      <div className="comparison-summary"><div><strong>{percent(data.arms.rag.completude.valor)}</strong><span>completas com RAG</span><small>{ratio(data.arms.rag.completude)} respondíveis</small></div><ArrowRight aria-hidden="true" /><div><strong>{percent(data.arms.llm.completude.valor)}</strong><span>completas com Gemini isolado</span><small>{ratio(data.arms.llm.completude)} respondíveis</small></div><p>O RAG atendeu mais perguntas deste conjunto. É um diagnóstico pequeno, com temas já usados em ajustes, sem avaliação cega independente.</p></div>
      <section className="report-section"><h2>A mesma pergunta. Duas formas de responder.</h2><p>RAG da rodada histórica: busca híbrida → reranker → até cinco trechos → Gemini com citações. Gemini isolado: a pergunta e suas instruções, sem documentos ou busca.</p><div className="quality-charts">
        <Bars label="Respostas completas" rag={data.arms.rag.completude} llm={data.arms.llm.completude} />
        <Bars label="Fatos corroborados pelas referências" rag={data.arms.rag.corroboracao} llm={data.arms.llm.corroboracao} />
        <Bars label="Correção de premissas falsas" rag={data.arms.rag.premissas} llm={data.arms.llm.premissas} />
        <Bars label="Reconhecimento de ausência" rag={data.arms.rag.ausencia} llm={data.arms.llm.ausencia} />
      </div></section>
      <section className="report-section"><h2>Quatro cenários, sem mudar o RAG.</h2><div className="scenario-grid">{Object.entries(data.scenarios).map(([id, arms]) => <article key={id}><span className="scenario-id">{id}</span><h3>{{ T1: 'Localização e siglas', T2: 'Serviços e procedimentos', T3: 'Premissas incorretas', T4: 'Dados ausentes ou atuais' }[id]}</h3><p>{id === 'T4' ? 'Ausências reconhecidas' : 'Respostas completas'}</p><b>RAG {ratio(id === 'T4' ? arms.rag.ausencia : arms.rag.completude)}</b><span>Gemini {ratio(id === 'T4' ? arms.llm.ausencia : arms.llm.completude)}</span></article>)}</div></section>
      <aside className="evaluation-notice"><strong>A precisão ainda precisa melhorar.</strong><p>Hit@5 de 100% significa que encontramos alguma evidência nas 12 perguntas respondíveis. Porém, somente {ratio(data.arms.rag.precisao_trechos)} dos trechos foram julgados relevantes, abaixo da meta de 40%. Nas respondíveis, {ratio(data.arms.rag.precisao_respondiveis)}, com meta de 50%.</p><p>O RAG também foi mais lento: {data.arms.rag.latencia_valida_s.media.toFixed(2)} s contra {data.arms.llm.latencia_valida_s.media.toFixed(2)} s. Houve {data.arms.rag.falhas_tecnicas} falhas em {data.arms.rag.tentativas} tentativas do RAG e {data.arms.llm.falhas_tecnicas} em {data.arms.llm.tentativas} do Gemini. As falhas continuam contabilizadas.</p></aside>
      <ChunkExample />
      <section className="report-section"><h2>Cada métrica, sem mistério.</h2><p>Abra uma medida para entender a fórmula, o exemplo e o método de avaliação. N/A significa que ela não se aplica ou não tem denominador.</p>
        <div className="metric-glossary">{metrics.map(metric => <details key={metric.key}><summary><span>{metric.name}{metric.goal !== undefined && <small>Meta local: {metric.key === 'persistencia' ? '1 · sucesso' : percent(metric.goal)}</small>}</span><span className="metric-value">RAG <b>{valueFor(data.arms.rag, metric.key, data)}</b><small>Gemini {valueFor(data.arms.llm, metric.key, data)}</small></span></summary>
          <div className="metric-explanation"><code>{metric.formula}</code><p>{metric.explanation}</p><blockquote>{metric.example}</blockquote><p><b>Como medir:</b> {metric.method}</p></div></details>)}</div>
      </section>
      <section className="report-section"><h2>As 15 perguntas da rodada</h2><div className="question-results">{data.questions.map(q => <details key={q.id}><summary><span><b>{q.id}</b> {q.pergunta}</span><small>{q.respondiveis ? 'Respondível' : 'Sem resposta na base'}</small></summary><p><b>Referência:</b> {q.referencia}</p>
        <p>{(['rag', 'llm'] as const).map(arm => {
          const j = data.judgments.find(j => j.qid === q.id && j.braco === arm);
          return <span key={arm}>{arm === 'rag' ? 'RAG: ' : ' · Gemini: '}{q.respondiveis ? j?.completa ? 'completa' : 'incompleta' : j?.ausencia_correta ? 'ausência reconhecida' : 'ausência não reconhecida'}</span>;
        })}</p>{q.evidencias.map((e, i) => <p key={i}>{e.source_id} · {e.trecho}</p>)}</details>)}</div></section>
      <section className="report-section methodology"><h2>Como ler esta avaliação</h2><p>{data.reviewer}</p><p>Usamos a primeira saída válida. Repetimos apenas falhas técnicas, até quatro tentativas na rodada histórica. As médias de latência consideram as saídas válidas; o esforço inclui todas as tentativas. Os tokens refletem somente usage disponível: 15/15 saídas do Gemini e 13/15 do RAG. Não são uma estimativa completa de custo.</p><p>Sem navegador para o Gemini, sem trocar o reranker ou o modelo entre cenários. As métricas de recuperação não se aplicam à LLM isolada. Zero rastreabilidade do Gemini significa ausência da cadeia documental preservada, não que todas as URLs estejam quebradas.</p><p>Persistência: {data.persistence.success ? 'confirmada' : 'não confirmada'} em {new Date(data.persistence.executedAt).toLocaleString('pt-BR')}. {data.currentBaseMatches === true ? 'A assinatura da base atual coincide com a rodada.' : data.currentBaseMatches === false ? 'A base atual difere da rodada; os resultados históricos não avaliam essa nova versão.' : 'Não foi possível comparar a assinatura da base atual.'}</p><details><summary>Rubrica e proveniência dos números</summary>{Object.entries(data.rubric).map(([key, text]) => <p key={key}><b>{key}:</b> {text}</p>)}{data.artifacts.map(a => <p key={a.path}><a href={`https://github.com/Muniz2811/FCTE-Campus/blob/main/${a.path}`} target="_blank" rel="noreferrer">{a.path}</a><code>SHA-256 {a.sha256}</code></p>)}</details></section>
    </>}
  </div>;
}

import { useState } from 'react';
import { motion } from 'motion/react';
import { Activity, Crosshair, FileCheck2, ShieldCheck } from 'lucide-react';
import { percent, type Evaluation, type HistoricalArm } from './model';

const views = { quality: 'Qualidade', retrieval: 'Recuperação', operation: 'Operação' } as const;
type View = keyof typeof views;
type Measure = { label: string; values: [number | null | undefined, number | null | undefined]; unit?: 'seconds' | 'tokens' };

function readout(value: number | null | undefined, unit?: Measure['unit']) {
  if (value == null) return 'N/A';
  if (unit === 'seconds') return `${value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} s`;
  if (unit === 'tokens') return `${value.toLocaleString('pt-BR')} tokens`;
  return percent(value);
}

export function MetricsDashboard({ data }: { data: Evaluation }) {
  const [view, setView] = useState<View>('quality');
  const { rag, llm } = data.arms;
  const measures: Record<View, Measure[]> = {
    quality: [
      { label: 'Respostas completas', values: [rag.completude.valor, llm.completude.valor] },
      { label: 'Fatos corroborados', values: [rag.corroboracao.valor, llm.corroboracao.valor] },
      { label: 'Correção de premissas', values: [rag.premissas.valor, llm.premissas.valor] },
      { label: 'Reconhecimento de ausência', values: [rag.ausencia.valor, llm.ausencia.valor] },
    ],
    retrieval: [
      { label: 'Hit@5', values: [rag.hit_at_5?.valor, null] },
      { label: 'Precisão dos trechos', values: [rag.precisao_trechos?.valor, null] },
      { label: 'Fundamentação factual', values: [rag.fundamentacao?.valor, null] },
      { label: 'Rastreabilidade', values: [rag.rastreabilidade.valor, llm.rastreabilidade.valor] },
    ],
    operation: [
      { label: 'Sucesso na primeira tentativa', values: [rag.sucesso_primeira_tentativa.valor, llm.sucesso_primeira_tentativa.valor] },
      { label: 'Latência média', values: [rag.latencia_valida_s.media, llm.latencia_valida_s.media], unit: 'seconds' },
      { label: 'Tokens informados', values: [rag.tokens_saidas_validas.totalTokenCount, llm.tokens_saidas_validas.totalTokenCount], unit: 'tokens' },
    ],
  };
  const headlines = [
    { title: 'Respostas completas', value: rag.completude.valor, detail: `Gemini ${percent(llm.completude.valor)}`, Icon: FileCheck2 },
    { title: 'Hit@5', value: rag.hit_at_5?.valor, detail: 'Consultas com evidência no top 5', Icon: Crosshair },
    { title: 'Precisão dos trechos', value: rag.precisao_trechos?.valor, detail: `Meta ${percent(.4)}`, Icon: Activity },
    { title: 'Rastreabilidade', value: rag.rastreabilidade.valor, detail: 'Citações até documento e versão', Icon: ShieldCheck },
  ];
  return <section className="metrics-dashboard" aria-label="Resumo da avaliação">
    <div className="metric-headlines">{headlines.map(({ title, value, detail, Icon }) => <article key={title}>
      <span className="section-icon" aria-hidden="true"><Icon size={17} /></span>
      <h2>{title}</h2><strong>{percent(value)}</strong><small>{detail}</small>
    </article>)}</div>
    <div className="metric-board">
      <section className="metric-chart" aria-label="Gráfico da rodada histórica">
        <header><h2>RAG × Gemini</h2>
          <div className="metric-switch" role="group" aria-label="Dimensão do gráfico">
            {(Object.keys(views) as View[]).map(id => <button key={id} type="button" aria-pressed={id === view} onClick={() => setView(id)}>{views[id]}</button>)}
          </div>
        </header>
        <div className="metric-legend"><span>RAG</span><span>Gemini isolado</span></div>
        <div className="metric-chart-rows" key={view}>{measures[view].map(({ label, values, unit }) => {
          const max = unit ? Math.max(...values.map(value => value ?? 0), 1e-6) : 1;
          return <div className="metric-chart-row" key={label}><h3>{label}</h3>
            {(['rag', 'llm'] as HistoricalArm[]).map((arm, index) => {
              const value = values[index];
              return <div className={`metric-series ${arm}`} key={arm}>
                <span className="sr-only">{arm === 'rag' ? 'RAG' : 'Gemini'}</span>
                <div className="metric-track" aria-hidden="true">{value != null && <motion.span
                  initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: .52, ease: 'easeOut' }}
                  style={{ width: `${Math.min(100, value / max * 100)}%` }} />}</div>
                <b>{readout(value, unit)}</b>
              </div>;
            })}
          </div>;
        })}</div>
        {view === 'operation' && <p className="metric-scale">Tempo e tokens têm escalas próprias. Uso informado em {rag.saidas_validas_com_usage}/{rag.tarefas} saídas do RAG e {llm.saidas_validas_com_usage}/{llm.tarefas} do Gemini.</p>}
      </section>
      <aside className="metric-insight">
        <Activity size={24} aria-hidden="true" />
        <h2>Encontrar evidência é só o primeiro passo</h2>
        <p>Hit@5 indica se apareceu algum trecho útil. A precisão mede quantos trechos realmente ajudaram.</p>
        <a href="#chunk-example">Ver exemplo interativo <span aria-hidden="true">↗</span></a>
      </aside>
    </div>
  </section>;
}

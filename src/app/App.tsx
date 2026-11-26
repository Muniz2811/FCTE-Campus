import { useEffect, useState, type CSSProperties } from 'react';
import { ChevronRight, ExternalLink, Plus } from 'lucide-react';
import { AssistantPanel } from '../knowledge/presentation/AssistantPanel';
import { GradePanel } from '../knowledge/presentation/GradePanel';
import { useChat } from '../knowledge/presentation/use-chat';
import { Brand } from '../design/Brand';
import { SectionIcon, type SectionId } from '../design/SectionIcon';
import { MetricsPanel } from '../evaluation/MetricsPanel';
import { LiveComparison } from '../evaluation/LiveComparison';
import { RouteExplainer } from '../evaluation/RouteExplainer';
import type { Evaluation } from '../evaluation/model';

export function App() {
  const chat = useChat(true);
  const [tab, setTab] = useState<SectionId>('chat');
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [evaluationError, setEvaluationError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    setEvaluationError('');
    void fetch(`${import.meta.env.BASE_URL}api/v1/evaluation`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Avaliação indisponível');
      const data = await response.json() as Evaluation;
      if (!data.arms?.rag || !data.arms?.llm || !Array.isArray(data.questions)) throw new Error('Formato inválido');
      if (active) setEvaluation(data);
    }).catch(() => { if (!active) return; if (!controller.signal.aborted) setEvaluationError('Não foi possível carregar a avaliação histórica. Confira o backend e tente novamente.');
      else setEvaluationError('A avaliação demorou a responder. Tente novamente.');
    }).finally(() => window.clearTimeout(timeout));
    return () => { active = false; controller.abort(); window.clearTimeout(timeout); };
  }, [revision]);
  const navigation = [{ id: 'chat', label: 'Conversa', short: 'Chat' },
    { id: 'grade', label: 'Minha grade', short: 'Grade' },
    { id: 'metrics', label: 'Métricas do RAG', short: 'Métricas' },
    { id: 'comparison', label: 'Comparar ao vivo', short: 'Comparar' },
    { id: 'route', label: 'Como funciona', short: 'Fluxo' }] as const;
  const skipTarget: Record<string, string> = { chat: '#campus-question', grade: '#grade-title', metrics: '#metrics-panel', comparison: '#comparison-question', route: '#route-panel' };
  const newConversation = () => {
    setTab('chat');
    chat.clear();
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('#campus-question')?.focus());
  };
  return <div className="chat-app">
    <a href={skipTarget[tab]} className="skip-link">Ir para o conteúdo</a>
    <aside className="workspace-sidebar" aria-label="Sobre o assistente">
      <Brand />
      <button className="new-conversation" aria-label="Nova conversa" onClick={newConversation} disabled={chat.pending}>
        <Plus size={18} aria-hidden="true" /><span className="sidebar-label">Nova conversa</span>
      </button>
      <nav className="workspace-navigation" aria-label="Seções" style={{ '--section-index': navigation.findIndex(item => item.id === tab) } as CSSProperties}>
        <span className="sidebar-selection" aria-hidden="true" />
        {navigation.map(({ id, label }) => <button key={id} aria-label={label} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>
          <SectionIcon section={id} /><span className="sidebar-label">{label}</span>
        </button>)}
      </nav>
      <div className="sidebar-bottom">
        {chat.health.status === 'ready' && <p className="base-summary"><span className="live-dot" />
          <span className="sidebar-label">{chat.health.sources} fontes · {chat.health.chunks} trechos na base</span>
        </p>}
        <a className="project-link" href="https://github.com/Muniz2811/FCTE-Campus" target="_blank" rel="noreferrer" aria-label="Conheça o projeto (nova aba)">
          <ExternalLink size={16} aria-hidden="true" /><span className="sidebar-label">Conheça o projeto</span>
        </a>
        <p className="academic-note">Grupo 09 · Residência em IA<br />Projeto acadêmico, não é um serviço oficial da UnB.</p>
      </div>
    </aside>
    <main className={`conversation-workspace ${tab !== 'chat' && tab !== 'grade' ? 'has-workspace-heading' : ''}`}>
      {tab !== 'chat' && tab !== 'grade' && <header className="workspace-heading">
        <div className="mobile-brand"><Brand /></div>
        <div className="workspace-crumb"><span>FCTE Campus</span><ChevronRight size={14} /><strong>{navigation.find(item => item.id === tab)?.label}</strong></div>
      </header>}
      <section className="workspace-view" hidden={tab !== 'chat'} aria-label="Conversa"><AssistantPanel active={tab === 'chat'} chat={chat} onNewConversation={newConversation} /></section>
      <section className="workspace-view" hidden={tab !== 'grade'} aria-label="Minha grade"><GradePanel /></section>
      <section className="workspace-view" hidden={tab !== 'metrics'} aria-label="Métricas do RAG"><MetricsPanel data={evaluation} error={evaluationError} reload={() => setRevision(v => v + 1)} /></section>
      <section className="workspace-view" hidden={tab !== 'comparison'} aria-label="Comparação ao vivo"><LiveComparison data={evaluation} /></section>
      <section className="workspace-view" hidden={tab !== 'route'} aria-label="Como funciona"><RouteExplainer /></section>
    </main>
    <nav className="mobile-navigation" aria-label="Seções">{navigation.map(({ id, label, short }) => <button key={id} aria-label={label} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><SectionIcon section={id} /><span>{short}</span></button>)}</nav>
  </div>;
}

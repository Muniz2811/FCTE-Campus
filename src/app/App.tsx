import { useEffect, useState } from 'react';
import { BarChart3, BookOpenText, ExternalLink, FlaskConical, MessageCircle, Plus, Route } from 'lucide-react';
import { AssistantPanel } from '../knowledge/presentation/AssistantPanel';
import { useChat } from '../knowledge/presentation/use-chat';
import { MonitorPanel } from '../evaluation/MonitorPanel';
import { Brand } from '../design/Brand';
import { MetricsPanel } from '../evaluation/MetricsPanel';
import { LiveComparison } from '../evaluation/LiveComparison';
import { RouteExplainer } from '../evaluation/RouteExplainer';
import type { Evaluation } from '../evaluation/model';

export function App() {
  const chat = useChat(true);
  const [tab, setTab] = useState('chat');
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
  const navigation = [{ id: 'chat', label: 'Conversa', Icon: MessageCircle },
    { id: 'metrics', label: 'Métricas do RAG', Icon: BarChart3 }, { id: 'comparison', label: 'Comparar ao vivo', Icon: FlaskConical },
    { id: 'monitor', label: 'Ao vivo', Icon: Route },
    { id: 'route', label: 'Como funciona', Icon: Route }];
  const skipTarget: Record<string, string> = { monitor: '#live-monitor', chat: '#campus-question', metrics: '#metrics-panel', comparison: '#comparison-question', route: '#route-panel' };
  const newConversation = () => {
    setTab('chat');
    chat.clear();
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('#campus-question')?.focus());
  };
  return <div className="chat-app">
    <a href={skipTarget[tab]} className="skip-link">Ir para o conteúdo</a>
    <aside className="workspace-sidebar" aria-label="Sobre o assistente">
      <Brand />
      <nav className="workspace-navigation" aria-label="Seções">{navigation.map(({ id, label, Icon }) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><Icon size={19} />{label}</button>)}</nav>
      <button className="new-conversation" onClick={newConversation} disabled={chat.pending}>
        <Plus size={18} />Nova conversa
      </button>
      <div className="sidebar-about">
        <BookOpenText size={24} strokeWidth={1.5} />
        <h2>Conhecimento que<br />vem do campus.</h2>
        <p>Documentos e registros reunidos pela equipe para ajudar você a encontrar informação sobre a FCTE.</p>
      </div>
      <div className="sidebar-bottom">
        {chat.health.status === 'ready' && <p className="base-summary"><span className="live-dot" />
          {chat.health.sources} fontes · {chat.health.chunks} trechos na base
        </p>}
        <a className="project-link" href="https://github.com/Muniz2811/FCTE-Campus" target="_blank" rel="noreferrer">
          Conheça o projeto<ExternalLink size={14} /><span className="sr-only"> (nova aba)</span>
        </a>
        <p className="academic-note">Grupo 09 · Residência em IA<br />Projeto acadêmico, não é um serviço oficial da UnB.</p>
      </div>
    </aside>
    <main className="conversation-workspace">
      <section className="workspace-view" hidden={tab !== 'chat'} aria-label="Conversa"><AssistantPanel chat={chat} onNewConversation={newConversation} /></section>
      <section className="workspace-view" hidden={tab !== 'metrics'} aria-label="Métricas do RAG"><MetricsPanel data={evaluation} error={evaluationError} reload={() => setRevision(v => v + 1)} /></section>
      <section className="workspace-view" hidden={tab !== 'comparison'} aria-label="Comparação ao vivo"><LiveComparison data={evaluation} /></section>
      {tab === 'monitor' && <section className="workspace-view"><MonitorPanel /></section>}
      <section className="workspace-view" hidden={tab !== 'route'} aria-label="Como funciona"><RouteExplainer /></section>
    </main>
    <nav className="mobile-navigation" aria-label="Seções">{navigation.map(({ id, label, Icon }) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><Icon size={20} /><span>{label}</span></button>)}</nav>
  </div>;
}

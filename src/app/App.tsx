import { BookOpenText, ExternalLink, Plus } from 'lucide-react';
import { AssistantPanel } from '../knowledge/presentation/AssistantPanel';
import { useChat } from '../knowledge/presentation/use-chat';
import { Brand } from '../design/Brand';

export function App() {
  const chat = useChat(true);
  const newConversation = () => {
    chat.clear();
    document.querySelector<HTMLTextAreaElement>('#campus-question')?.focus();
  };
  return <div className="chat-app">
    <a href="#campus-question" className="skip-link">Ir para a pergunta</a>
    <aside className="workspace-sidebar" aria-label="Sobre o assistente">
      <Brand />
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
      <AssistantPanel chat={chat} onNewConversation={newConversation} />
    </main>
  </div>;
}

import { ArrowUp, ArrowUpRight, BookOpenText, Check, ChevronRight, LoaderCircle, Plus, RefreshCw, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { Brand } from '../../design/Brand';
import { ChatAnswer } from './ChatAnswer';
import type { useChat } from './use-chat';

const suggestions = [
  'Onde fica o laboratório COSMOS?',
  'Quais espaços de estudo a biblioteca oferece?',
  'Pessoas de fora da UnB podem usar a biblioteca?',
];

export function AssistantPanel({ chat, onNewConversation }: {
  chat: ReturnType<typeof useChat>; onNewConversation(): void;
}) {
  const { draft, setDraft } = chat;
  const body = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const reduced = useReducedMotion();
  const [copied, setCopied] = useState(false);
  const connected = chat.health.status === 'ready' && chat.health.generationConfigured;
  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight, behavior: reduced ? 'instant' : 'smooth' });
  }, [chat.messages.length, chat.pending, reduced]);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = 'auto';
    input.current.style.height = `${Math.min(input.current.scrollHeight, 168)}px`;
  }, [draft]);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(timer);
  }, [copied]);
  const send = (question: string) => {
    if (!connected || chat.pending || !question.trim()) return;
    setDraft('');
    void chat.send(question);
  };
  const copyConversation = async () => {
    const text = chat.messages.map(m => `${m.role === 'user' ? 'Você' : 'Assistente FCTE'}\n${m.role === 'user' ? m.text
      : m.result.status === 'answered' ? `${m.result.answer}\n\n${m.result.sources.map((s, i) => `[${i+1}] ${s.title} — ${s.url || s.sourceId || s.id}`).join('\n')}`
        : m.result.message}`).join('\n\n');
    try { await navigator.clipboard.writeText(text); setCopied(true); }
    catch { /* A conversa continua disponível para seleção e cópia manual. */ }
  };
  return <section className="chat-panel" aria-label="Chat com as fontes do campus">
    <header className="chat-heading">
      <div className="mobile-brand"><Brand /></div>
      <div className="desktop-heading"><span className="heading-dot" /><strong>Assistente FCTE</strong><ChevronRight size={13} /><span>Campus Gama</span></div>
      <div className="chat-actions">
        {chat.messages.length > 0 && <button className="copy-conversation" aria-label="Copiar conversa com as fontes" onClick={() => void copyConversation()}>
          {copied && <Check size={14} />}{copied ? 'Copiado' : 'Copiar'}
        </button>}
        <button className="icon-button mobile-new" aria-label="Iniciar nova conversa" onClick={onNewConversation} disabled={chat.pending}><Plus size={21} /></button>
        <span className={`connection-status ${connected ? 'is-connected' : ''}`} role="status">
          <span />{connected ? 'Base conectada' : chat.health.status === 'loading' || chat.health.status === 'idle' ? 'Conectando' : 'Sem conexão'}
        </span>
      </div>
    </header>
    <div className="chat-body" ref={body}>
      <div className={`conversation-content ${!chat.messages.length ? 'is-empty' : ''}`}>
        {!chat.messages.length && <motion.div className="chat-welcome" initial={false} animate={{ opacity: 1 }}>
          <div className="welcome-mark" aria-hidden="true"><BookOpenText size={38} strokeWidth={1.35} /><span /></div>
          <h1>O que você quer saber<br /><span>sobre a FCTE?</span></h1>
          <p>Encontre informações sobre espaços, laboratórios e serviços do campus. Cada resposta mostra de onde veio a informação.</p>
          <div className="chat-suggestions" aria-label="Sugestões de perguntas">
            {suggestions.map(question => <button key={question} disabled={!connected || chat.pending} onClick={() => send(question)}>
              <span>{question}</span><ArrowUpRight size={19} />
            </button>)}
          </div>
        </motion.div>}
        {chat.health.status === 'unavailable' && <div className="chat-connection" role="status">
          <p>{chat.health.message}</p><button className="text-button" onClick={() => void chat.refresh()}><RefreshCw size={15} />Verificar conexão</button>
        </div>}
        {chat.health.status === 'ready' && !chat.health.generationConfigured && <div className="chat-connection" role="status">
          <p>A base está disponível, mas a geração de respostas ainda não foi configurada no servidor.</p>
          <button className="text-button" onClick={() => void chat.refresh()}><RefreshCw size={15} />Verificar novamente</button>
        </div>}
        <div className="chat-messages" role="log" aria-label="Conversa" aria-live="polite" aria-relevant="additions">
          {chat.messages.map(message => <motion.article key={message.id} className={`chat-message chat-message--${message.role}`}
            initial={{ opacity: 0, y: reduced ? 0 : 7 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .2 }}>
            <span className="chat-message-label">{message.role === 'user' ? 'Você' : <><BookOpenText size={17} />Assistente FCTE</>}</span>
            {message.role === 'user' ? <p>{message.text}</p> : <ChatAnswer result={message.result} onRetry={() => void chat.send(message.question)} />}
          </motion.article>)}
          {chat.pending && <div className="chat-pending" role="status"><LoaderCircle size={18} className="chat-spinner" /><span>Consultando as fontes do campus…</span></div>}
        </div>
      </div>
    </div>
    <div className="composer-wrap">
      <form className="chat-composer" onSubmit={event => { event.preventDefault(); send(draft); }}>
        <label htmlFor="campus-question" className="sr-only">Sua pergunta sobre o campus</label>
        <div className="chat-input-row">
          <textarea ref={input} id="campus-question" name="question" value={draft} onChange={event => setDraft(event.target.value)} maxLength={1200} rows={1} enterKeyHint="send" placeholder="Pergunte sobre o campus…"
            onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(draft); } }} />
          {chat.pending ? <button type="button" className="chat-send" aria-label="Parar de aguardar resposta" onClick={chat.cancel}><Square size={16} fill="currentColor" /></button>
            : <button type="submit" className="chat-send" aria-label="Enviar pergunta" disabled={!connected || !draft.trim()}><ArrowUp size={22} /></button>}
        </div>
      </form>
      <p className="composer-note">A IA pode errar. Confira as fontes antes de usar a informação.</p>
    </div>
  </section>;
}

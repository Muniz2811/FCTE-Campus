import { ArrowUpRight, LoaderCircle, MessageCircle, Plus, RefreshCw, Send, Square } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { ChatAnswer } from './ChatAnswer';
import type { useChat } from './use-chat';

const suggestions = ['Onde fica o laboratório COSMOS?', 'Que espaços de estudo a biblioteca oferece?', 'A sala I10 está livre agora?'];
export function AssistantPanel({ chat }: { chat: ReturnType<typeof useChat> }) {
  const { draft, setDraft } = chat;
  const body = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const connected = chat.health.status === 'ready' && chat.health.generationConfigured;
  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: reduced ? 'instant' : 'smooth' }); }, [chat.messages.length, chat.pending, reduced]);
  const send = (question: string) => { if (!connected || chat.pending || !question.trim()) return; setDraft(''); void chat.send(question); };
  return <section className="chat-panel" aria-label="Chat com as fontes do campus">
    <header className="chat-heading"><span className="chat-avatar"><MessageCircle size={22} /></span>
      <div><h1>Assistente FCTE</h1><p>{connected ? `${chat.health.status === 'ready' ? chat.health.sources : 0} fontes · RAG local` : 'Perguntas com fontes, sem adivinhação.'}</p></div>
      <button className="icon-button" aria-label="Iniciar nova conversa" disabled={chat.pending || !chat.messages.length} onClick={chat.clear}><Plus size={21} /></button></header>
    <div className="chat-body" ref={body}>
      {chat.health.status === 'loading' && <p className="chat-connection" role="status"><LoaderCircle size={16} className="chat-spinner" />Conectando ao RAG local…</p>}
      {chat.health.status === 'unavailable' && <div className="chat-connection chat-connection--error" role="status"><p>{chat.health.message}</p><button className="text-button" onClick={() => void chat.refresh()}><RefreshCw size={15} />Verificar conexão</button></div>}
      {chat.health.status === 'ready' && !chat.health.generationConfigured && <div className="chat-connection chat-connection--error" role="status"><p>A base está aberta. Falta configurar a chave do Gemini no backend para gerar respostas.</p><button className="text-button" onClick={() => void chat.refresh()}>Verificar novamente</button></div>}
      {!chat.messages.length && <div className="chat-welcome"><div className="chat-welcome-icon"><MessageCircle size={36} strokeWidth={1.4} /></div>
        <h2>O que você quer<br />descobrir no campus?</h2><p>Pergunte sobre prédios, laboratórios e serviços. Confira os documentos usados em cada resposta.</p>
        <div className="chat-suggestions">{suggestions.map(question => <button key={question} disabled={!connected || chat.pending} onClick={() => send(question)}><span>{question}</span><ArrowUpRight size={17} /></button>)}</div>
      </div>}
      <div className="chat-messages" role="log" aria-label="Mensagens da consulta" aria-live="polite" aria-relevant="additions">
        {chat.messages.map(message => <motion.div key={message.id} className={`chat-message chat-message--${message.role}`} initial={{ opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .18 }}>
          <span className="chat-message-label">{message.role === 'user' ? 'Você' : 'Assistente FCTE'}</span>
          {message.role === 'user' ? <p>{message.text}</p> : <ChatAnswer result={message.result} onRetry={() => void chat.send(message.question)} />}
        </motion.div>)}
        {chat.pending && <div className="chat-pending" role="status"><LoaderCircle size={16} className="chat-spinner" />Consultando a base e o Gemini…</div>}
      </div>
    </div>
    <form className="chat-composer" onSubmit={event => { event.preventDefault(); send(draft); }}>
      <label htmlFor="campus-question" className="sr-only">Sua pergunta sobre o campus</label>
      <div className="chat-input-row"><textarea id="campus-question" name="question" value={draft} onChange={event => setDraft(event.target.value)} maxLength={1200} rows={2} enterKeyHint="send" placeholder="Pergunte sobre a FCTE…" disabled={!connected}
        onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(draft); } }} />
        {chat.pending ? <button type="button" className="chat-send" aria-label="Parar de aguardar resposta" onClick={chat.cancel}><Square size={17} fill="currentColor" /></button>
          : <button type="submit" className="chat-send" aria-label="Enviar pergunta" disabled={!connected || !draft.trim()}><Send size={19} /></button>}</div>
      <p>Você pode complementar a pergunta anterior. Confira as fontes; a IA pode errar.</p>
    </form>
  </section>;
}

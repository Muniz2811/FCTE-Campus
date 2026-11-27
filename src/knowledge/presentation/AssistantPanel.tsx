import { ArrowUp, Check, Pause, Play, Plus, RefreshCw, Square } from 'lucide-react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { LiquidButton } from '../../design/liquid-glass/LiquidButton';
import { AlternarTema } from '../../design/tema/AlternarTema';
import { motion, useReducedMotion } from 'motion/react';
import { Brand } from '../../design/Brand';
import { CampusScene } from '../../design/CampusScene';
import { LiquidGlass } from '../../design/liquid-glass/LiquidGlass';
import { Mascote, type MascoteEstado } from '../../design/mascote/Mascote';
import { MascoteMini } from '../../design/mascote/MascoteMini';
import { ChatAnswer } from './ChatAnswer';
import type { useChat } from './use-chat';

const suggestions = [
  { label: 'Onde fica o laboratório COSMOS?', question: 'Onde fica o laboratório COSMOS?' },
  { label: 'Espaços de estudo da biblioteca', question: 'Quais espaços de estudo a biblioteca oferece?' },
  { label: 'Biblioteca para visitantes', question: 'Pessoas de fora da UnB podem usar a biblioteca?' },
];
// Tamanho em que o livro é desenhado; no hero ele aparece reduzido, na conversa quase no tamanho cheio.
const BASE_MASCOTE = 520;

export function AssistantPanel({ active, chat, onNewConversation }: {
  active: boolean; chat: ReturnType<typeof useChat>; onNewConversation(): void;
}) {
  const { draft, setDraft } = chat;
  const painel = useRef<HTMLElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const vagaHero = useRef<HTMLDivElement>(null);
  const composerRow = useRef<HTMLDivElement>(null);
  const palco = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const [copied, setCopied] = useState(false);
  const [orbitPaused, setOrbitPaused] = useState(false);
  const [alvo, setAlvo] = useState({ x: 0, y: 0, escala: 1, pronto: false });
  const [espaco, setEspaco] = useState(0);
  const [digitando, setDigitando] = useState(false);
  const [comemorando, setComemorando] = useState(false);
  const [pulso, setPulso] = useState(0);
  const hasMessages = chat.messages.length > 0;
  const connected = chat.health.status === 'ready' && chat.health.generationConfigured;
  const ultima = chat.messages.at(-1);
  // Trechos citados na última resposta: acendem no mapa da base.
  const destaques = useMemo(() => {
    const resposta = [...chat.messages].reverse().find(m => m.role === 'assistant' && m.result.status === 'answered');
    return resposta?.role === 'assistant' && resposta.result.status === 'answered' ? resposta.result.sources.map(s => s.id) : [];
  }, [chat.messages]);

  // Boas-vindas: o livro fica na vaga do hero. Conversa: ele desce e fica enorme, espiando por
  // baixo do composer com os olhos logo acima dele (referência: Interactive-studio-footer-concept).
  const medir = useCallback(() => {
    const p = painel.current?.getBoundingClientRect();
    if (!p) return;
    if (!hasMessages) {
      const r = vagaHero.current?.getBoundingClientRect();
      if (!r || !r.width) return;
      setAlvo({ x: r.left - p.left + r.width / 2 - BASE_MASCOTE / 2, y: r.top - p.top + r.height / 2 - BASE_MASCOTE / 2, escala: r.width / BASE_MASCOTE, pronto: true });
      return;
    }
    const c = composerRow.current?.getBoundingClientRect();
    if (!c) return;
    const tamanho = Math.min(Math.max(p.width * .32, 240), 440);
    const topoComposer = c.top - p.top;
    // Os olhos ficam a 53% da altura do desenho (desenhados maiores e mais baixos ao olhar para
    // baixo), o topo do livro a ~24%. A folga de 56px mantém os olhos acima do composer.
    const topo = topoComposer - .53 * tamanho - 56;
    const centroX = c.left - p.left + c.width / 2;
    setAlvo({ x: centroX - BASE_MASCOTE / 2, y: topo + tamanho / 2 - BASE_MASCOTE / 2, escala: tamanho / BASE_MASCOTE, pronto: true });
    setEspaco(Math.max(0, topoComposer - (topo + .24 * tamanho)));
  }, [hasMessages]);
  useLayoutEffect(() => {
    medir();
    const ro = new ResizeObserver(medir);
    for (const el of [painel.current, vagaHero.current, composerRow.current]) if (el) ro.observe(el);
    return () => ro.disconnect();
  }, [medir]);

  // Resposta nova: onda no fundo e o livro comemora por um instante.
  useEffect(() => {
    if (ultima?.role !== 'assistant' || ultima.result.status !== 'answered') return;
    setPulso(v => v + 1);
    setComemorando(true);
    const timer = setTimeout(() => setComemorando(false), 2600);
    return () => clearTimeout(timer);
  }, [ultima]);

  useEffect(() => {
    const viewport = body.current;
    if (!viewport) return;
    viewport.scrollTo({ top: chat.messages.length ? viewport.scrollHeight : 0, behavior: reduced || !chat.messages.length ? 'instant' : 'smooth' });
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
    setDigitando(false);
    void chat.send(question);
  };
  const copyConversation = async () => {
    const text = chat.messages.map(m => `${m.role === 'user' ? 'Você' : 'FCTE Campus'}\n${m.role === 'user' ? m.text
      : m.result.status === 'answered' ? `${m.result.answer}\n\n${m.result.sources.map((s, i) => `[${i + 1}] ${s.title}, ${s.url || s.sourceId || s.id}`).join('\n')}`
        : m.result.message}`).join('\n\n');
    try { await navigator.clipboard.writeText(text); setCopied(true); }
    catch { /* A conversa continua disponível para seleção e cópia manual. */ }
  };

  // Sem base: espera. Uma resposta que falhou: bloqueado. Consulta: pensando. Resposta nova: comemora.
  // Na conversa o livro é gigante: estados com marca (pontinhos de "pensando", "!" de bloqueado,
  // anéis de "pronto") trocariam o corpo por formas enormes. Lá ele usa só estados de corpo e olhar.
  const estado: MascoteEstado = chat.pending ? (hasMessages ? 'lendo' : 'thinking')
    : ultima?.role === 'assistant' && ultima.result.status === 'unavailable' ? (hasMessages ? 'waiting' : 'blocked')
      : chat.health.status === 'unavailable' ? 'waiting'
        : comemorando ? 'feliz' : 'idle';

  return <section ref={painel} className={`chat-panel assistant-panel ${hasMessages ? 'has-messages' : ''} ${chat.pending ? 'is-pending' : ''}`}
    style={{ '--espaco-mascote': `${espaco}px` } as CSSProperties} aria-label="Chat com as fontes do campus">
    <CampusScene paused={!active || orbitPaused || !!reduced} focused={hasMessages} pending={chat.pending} pulso={pulso} ancora={palco}
      destaques={destaques} total={chat.health.status === 'ready' ? chat.health.chunks : 214} />
    <motion.div ref={palco} className={`mascote-palco ${hasMessages ? 'is-espiando' : ''}`} style={{ width: BASE_MASCOTE, height: BASE_MASCOTE }}
      initial={false}
      animate={{ x: alvo.x, y: alvo.y, scale: alvo.escala, opacity: alvo.pronto ? 1 : 0 }}
      transition={reduced ? { duration: 0 } : { type: 'spring', stiffness: 140, damping: 19, mass: .9 }}>
      {/* Segue o cursor pela página; enquanto você digita, olha para o campo de texto. */}
      <Mascote estado={estado} className="mascote" followPointer={!reduced} olhar={digitando && !chat.pending ? { x: 0, y: .85 } : null} />
    </motion.div>
    <header className="chat-heading">
      <div className="mobile-brand"><Brand /></div>
      <div className="chat-actions">
        {!hasMessages && !reduced && <button className="orbit-toggle icon-button" type="button"
          aria-label={orbitPaused ? 'Retomar animação do fundo' : 'Pausar animação do fundo'}
          onClick={() => setOrbitPaused(value => !value)}>
          {orbitPaused ? <Play size={16} /> : <Pause size={16} />}
        </button>}
        {hasMessages && <button className="copy-conversation" aria-label="Copiar conversa com as fontes" onClick={() => void copyConversation()}>
          {copied && <Check size={14} />}{copied ? 'Copiado' : 'Copiar'}
        </button>}
        <button className="icon-button mobile-new" aria-label="Iniciar nova conversa" onClick={onNewConversation} disabled={chat.pending}><Plus size={21} /></button>
        <AlternarTema className="mobile-theme" />
        <LiquidGlass as="span" raio={99} refracao={false} className={`connection-status ${connected ? 'is-connected' : ''}`} role="status">
          <span />{connected ? 'Base conectada' : chat.health.status === 'loading' || chat.health.status === 'idle' ? 'Conectando' : 'Sem conexão'}
        </LiquidGlass>
      </div>
    </header>
    <div className="chat-body" ref={body}>
      <div className={`conversation-content ${!hasMessages ? 'is-empty' : ''}`}>
        {!hasMessages && <div className="chat-welcome">
          <div className="campus-hero">
            <div className="campus-hero-copy">
              <h1>Pergunte sobre o campus <span>da FCTE.</span></h1>
              <p>Laboratórios, espaços de estudo e serviços da UnB Gama, com a fonte de cada resposta.</p>
              <div className="chat-suggestions" role="group" aria-label="Sugestões de perguntas">
                {suggestions.map(({ label, question }, i) => <LiquidGlass as="button" type="button" raio={18} key={question}
                  style={{ animationDelay: `${.12 + i * .07}s` }} disabled={!connected || chat.pending} onClick={() => send(question)}>
                  {label}
                </LiquidGlass>)}
              </div>
            </div>
            <div className="mascote-vaga mascote-vaga--hero" ref={vagaHero} aria-hidden="true" />
          </div>
        </div>}
        {chat.health.status === 'unavailable' && <LiquidGlass className="chat-connection" raio={18} role="status">
          <p>{chat.health.message}</p><button className="text-button" onClick={() => void chat.refresh()}><RefreshCw size={15} />Verificar conexão</button>
        </LiquidGlass>}
        {chat.health.status === 'ready' && !chat.health.generationConfigured && <LiquidGlass className="chat-connection" raio={18} role="status">
          <p>A base está disponível, mas a geração de respostas ainda não foi configurada no servidor.</p>
          <button className="text-button" onClick={() => void chat.refresh()}><RefreshCw size={15} />Verificar novamente</button>
        </LiquidGlass>}
        <div className="chat-messages" role="log" aria-label="Conversa" aria-live="polite" aria-relevant="additions">
          {chat.messages.map(message => <motion.article key={message.id} className={`chat-message chat-message--${message.role}`}
            initial={{ opacity: 0, y: reduced ? 0 : 14, filter: reduced ? 'none' : 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ duration: .45, ease: [.16, 1, .3, 1] }}>
            <span className="chat-message-label">{message.role === 'user' ? 'Você' : <><MascoteMini />FCTE Campus</>}</span>
            {message.role === 'user' ? <p>{message.text}</p> : <ChatAnswer result={message.result} onRetry={() => void chat.send(message.question)} />}
          </motion.article>)}
          {chat.pending && <LiquidGlass className="chat-pending" raio={99} role="status">
            <span className="pending-spinner" aria-hidden="true" />
            <strong>Lendo as fontes do campus</strong>
          </LiquidGlass>}
        </div>
      </div>
    </div>
    <div className="composer-wrap">
      <div className="composer-row" ref={composerRow}>
        <LiquidGlass as="form" raio={24} className="chat-composer" onSubmit={event => { event.preventDefault(); send(draft); }}>
          <label htmlFor="campus-question" className="sr-only">Sua pergunta sobre o campus</label>
          <div className="chat-input-row">
            <textarea ref={input} id="campus-question" name="question" value={draft} onChange={event => { setDraft(event.target.value); setDigitando(!!event.target.value); }}
              onBlur={() => setDigitando(false)} onFocus={event => setDigitando(!!event.target.value)} maxLength={1200} rows={1} enterKeyHint="send" placeholder="Pergunte sobre o campus…"
              onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(draft); } }} />
            {chat.pending ? <LiquidButton type="button" className="chat-send" aria-label="Parar de aguardar resposta" onClick={chat.cancel}><Square size={16} fill="currentColor" /></LiquidButton>
              : <LiquidButton type="submit" className="chat-send" aria-label="Enviar pergunta" disabled={!connected || !draft.trim()}><ArrowUp size={22} /></LiquidButton>}
          </div>
        </LiquidGlass>
      </div>
      <p className="composer-note">A IA pode errar. Confira as fontes antes de usar a informação.</p>
    </div>
  </section>;
}

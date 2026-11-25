import { useEffect, useState } from 'react';
import './monitor.css';

type Span = {
  trace: string; span: string; parent?: string; etapa: string; inicio: string;
  estado: string; detalhe?: string; modelo?: string; ms?: number; trechos?: number; tokens?: number; http?: number;
};
const hora = (s: Span) => new Date(s.inicio).toLocaleTimeString('pt-BR');

function Ramo({ item, spans }: { item: Span; spans: Span[] }) {
  const filhos = spans.filter(s => s.parent === item.span && s.span !== item.span);
  return <li><div className="monitor-node" data-status={item.estado}>
    <strong>{item.etapa}</strong> <span>{item.estado}</span>
    <small>{[item.detalhe, item.modelo, item.ms != null && `${item.ms} ms`,
      item.tokens != null && `${item.tokens} tokens`, item.trechos != null && `${item.trechos} trechos`,
      item.http && `HTTP ${item.http}`].filter(Boolean).join(' · ')}</small>
  </div>{filhos.length > 0 && <ul>{filhos.map(s => <Ramo key={s.span} item={s} spans={spans} />)}</ul>}</li>;
}

export function MonitorPanel() {
  const [token, setToken] = useState('');
  const [senha, setSenha] = useState('');
  const [runs, setRuns] = useState<Span[][]>([]);
  const [selecionado, selecionar] = useState('');
  const [status, setStatus] = useState('');
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    let timer: number;
    async function atualizar() {
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}api/v1/monitor`, {
          signal: controller.signal, headers: { Authorization: 'Bearer ' + token }, cache: 'no-store',
        });
        if (res.status === 401) {
          setStatus('Token de leitura inválido ou ausente na configuração do backend.');
          setToken(''); setRuns([]); return;
        }
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (!Array.isArray(data.execucoes)) throw new Error();
        setRuns(data.execucoes); setStatus('Atualizado às ' + new Date().toLocaleTimeString('pt-BR'));
      } catch {
        if (!controller.signal.aborted) setStatus('Conexão interrompida. Reconectando…');
      }
      if (!controller.signal.aborted) timer = window.setTimeout(atualizar, 1500);
    }
    setStatus('Conectando…'); void atualizar();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [token]);
  const spans = [...(runs.find(r => r[0]?.trace === selecionado) ?? runs[0] ?? [])]
    .sort((a, b) => Date.parse(a.inicio) - Date.parse(b.inicio));
  return <div className="evaluation-page monitor-page" id="live-monitor">
    <header className="evaluation-heading"><h1>Fluxo ao vivo</h1>
      <p>Acompanhe o encaminhamento do Milton e as etapas executadas pelo RAG.</p></header>
    {!token ? <form onSubmit={e => { e.preventDefault(); setToken(senha.trim()); setSenha(''); }}>
      <label>Token de leitura<input required type="password" value={senha} onChange={e => setSenha(e.target.value)} /></label>
      <button>Conectar</button></form> : <>
      <label>Execução<select value={runs.some(r => r[0]?.trace === selecionado) ? selecionado : ''}
        onChange={e => selecionar(e.target.value)}><option value="">Acompanhar a mais recente</option>
        {runs.map(r => <option key={r[0].trace} value={r[0].trace}>{hora(r[0])} · {r[0].trace.slice(0, 8)}</option>)}
      </select></label>
      {spans.length ? <><p>Execução {spans[0].trace}</p><ul className="monitor-tree">
        {spans.filter(s => !spans.some(p => p.span === s.parent)).map(s => <Ramo key={s.span} item={s} spans={spans} />)}
      </ul></> : <p>Aguardando execuções.</p>}
    </>}
    <small>{status}</small>
  </div>;
}

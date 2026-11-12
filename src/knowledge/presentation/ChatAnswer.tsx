import { BookOpen, ExternalLink, Layers } from 'lucide-react';
import type { KnowledgeResult, KnowledgeSource } from '../application/assistant';

function References({ sources, label }: { sources: KnowledgeSource[]; label: string }) {
  return <details className="chat-references"><summary><BookOpen size={15} />{label} ({sources.length})</summary>
    <ol>{sources.map(source => <li key={source.id}>
      <strong>{source.title}</strong>
      {source.section && <span className="source-section">{source.section}</span>}
      <p>{source.excerpt}</p>
      <span className="source-version">{source.sourceId ?? source.id} · versão {source.version}{source.reviewedAt ? ` · revisão ${source.reviewedAt}` : ''}</span>
      <span className="source-version">{source.validUntil === 'desconhecida' ? 'Vigência não informada pela fonte.' : source.validUntil ? `Validade: ${source.validUntil}` : ''}</span>
      {source.distance !== undefined && <span className="source-version">Distância cosseno: {source.distance.toFixed(4)} · não é uma probabilidade de verdade.</span>}
      {source.url && <a href={source.url} target="_blank" rel="noreferrer">Abrir documento original <ExternalLink size={13} /><span className="sr-only"> (nova aba)</span></a>}
    </li>)}</ol>
  </details>;
}

export function ChatAnswer({ result, onRetry }: { result: KnowledgeResult; onRetry(): void }) {
  return <div className={`chat-answer chat-answer--${result.status}`}>
    <p className="chat-answer-text">{result.status === 'answered' ? result.answer : result.message}</p>
    {result.status === 'unavailable' && <button className="text-button" onClick={onRetry}>Tentar novamente</button>}
    {result.status === 'answered' && <References sources={result.sources} label="Fontes utilizadas" />}
    {!!result.retrieved?.length && <div className="retrieved-sources"><References sources={result.retrieved} label="Trechos recuperados" /></div>}
    {result.requestId && <details className="chat-execution"><summary><Layers size={13} />Registro da consulta</summary>
      <p>Modelo: {result.model}<br />Execução: {result.requestId}<br />Base: {result.baseVersion}</p>
    </details>}
  </div>;
}

import { LiquidButton } from '../../design/liquid-glass/LiquidButton';
import { AlternarTema } from '../../design/tema/AlternarTema';
import { BookOpen, CalendarDays, FileUp, MapPin, ShieldCheck, Square, TriangleAlert, X } from 'lucide-react';
import type { CSSProperties } from 'react';
import type { GradeCitation, GradeClass, GradeDay, GradeResult } from '../application/grade';
import { Brand } from '../../design/Brand';
import { useGrade } from './use-grade';
import { ImportacaoComprovante, type FaseImportacao } from '../../design/importacao/ImportacaoComprovante';

const dayName: Record<GradeDay, string> = { seg: 'Segunda', ter: 'Terça', qua: 'Quarta', qui: 'Quinta', sex: 'Sexta', sab: 'Sábado' };
const sizeLabel = (bytes: number) => bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

function Citations({ citations }: { citations: GradeCitation[] }) {
  const groups = [{ origin: 'comprovante', label: 'Do seu comprovante' }, { origin: 'base', label: 'Da base do campus' }] as const;
  return <div className="grade-citations">{groups.map(({ origin, label }) => {
    const items = citations.filter(c => c.origin === origin);
    return items.length ? <details key={origin} className="chat-references" open><summary><BookOpen size={15} />{label} ({items.length})</summary>
      <ol>{items.map(c => <li key={c.n} value={c.n}>
        <strong>{origin === 'comprovante' ? `Componente ${c.reference}` : c.reference}</strong>
        <p>{c.excerpt}</p>
        {c.version && <span className="source-version">versão {c.version}</span>}
      </li>)}</ol>
    </details> : null;
  })}</div>;
}

function ClassCard({ item, index }: { item: GradeClass; index: number }) {
  return <article className="grade-class" style={{ '--i': index } as CSSProperties}>
    <header>
      <h3><span>{item.code}</span>{item.name ?? 'Componente sem nome lido'}</h3>
      <p>{[item.group, item.hours ? `${item.hours}h` : undefined].filter(Boolean).join(' · ')}</p>
      {item.status && <span className="grade-status">{item.status}</span>}
    </header>
    {item.meetings.length ? <ul className="grade-meetings" aria-label={`Horários de ${item.code}`}>
      {item.meetings.map(m => <li key={`${m.day}${m.start}`}><CalendarDays size={15} /><strong>{dayName[m.day]}</strong> {m.start}–{m.end}</li>)}
    </ul> : <p className="grade-empty">Nenhum horário lido para esta turma.</p>}
    <div className="grade-places">
      <p className="grade-declared"><MapPin size={15} />No comprovante: <strong>{item.declaredPlace ?? 'não informado'}</strong></p>
      {item.places.map(place => <p key={place.text} className="grade-place">
        <span><strong>{place.text}</strong> → {place.building}{place.floor ? `, ${place.floor}` : ' (andar não confirmado pela fonte)'}</span>
        <small>{place.sourceTitle} · versão {place.version}</small>
      </p>)}
    </div>
    {item.issues.length > 0 && <ul className="grade-issues" aria-label={`Pontos de atenção de ${item.code}`}>
      {item.issues.map(i => <li key={i.code + i.message}><TriangleAlert size={14} />{i.message}</li>)}
    </ul>}
  </article>;
}

function Result({ result }: { result: GradeResult }) {
  return <section className="grade-result" aria-label="Resultado da leitura">
    <div className="grade-summary">
      <h2>{result.period ? `Período ${result.period}` : 'Período não identificado'}</h2>
      <p>{result.classes.length} {result.classes.length === 1 ? 'turma lida' : 'turmas lidas'}</p>
    </div>
    {result.issues.length > 0 && <ul className="grade-issues grade-issues--global">{result.issues.map(i => <li key={i.code + i.message}><TriangleAlert size={14} />{i.message}</li>)}</ul>}
    {result.question && <div className="grade-answer">
      <span className="chat-message-label">Sua pergunta</span><p className="grade-question">{result.question}</p>
      <span className="chat-message-label grade-answer-label">Resposta</span>
      {result.answerStatus === 'indisponivel'
        ? <p className="chat-answer-text chat-answer--unavailable">Não foi possível gerar a resposta agora, mas a leitura do comprovante está abaixo.</p>
        : <p className={`chat-answer-text ${result.answerStatus === 'insuficiente' ? 'chat-answer--insufficient' : ''}`}>{result.answer}</p>}
      {result.citations.length > 0 && <Citations citations={result.citations} />}
    </div>}
    <div className="grade-classes">{result.classes.map((item, index) => <ClassCard key={`${item.code}-${index}`} item={item} index={index} />)}</div>
  </section>;
}

export function GradePanel() {
  const grade = useGrade();
  const note = 'Confira sempre o comprovante original: a leitura é feita por IA e pode errar.';
  const fase: FaseImportacao = grade.pending ? 'lendo' : grade.outcome?.status === 'ok' ? 'pronto' : grade.outcome?.status === 'unavailable' ? 'erro' : 'escolhido';
  return <section className="chat-panel grade-panel" aria-label="Minha grade">
    <header className="chat-heading">
      <div className="mobile-brand"><Brand /></div>
      <AlternarTema className="mobile-theme" />
    </header>
    <div className="chat-body"><div className="conversation-content grade-content">
      <div className="grade-intro">
        <h1 id="grade-title" tabIndex={-1}>Leia sua grade<br /><span> do comprovante de matrícula.</span></h1>
        <p>Envie o PDF ou um print do comprovante do SIGAA. Mostramos as turmas, os horários e onde ficam as salas, com a fonte de cada informação.</p>
        <p className="grade-privacy"><ShieldCheck size={16} />O arquivo é lido em memória e não é guardado nem indexado. O OCR local identifica as tabelas. A IA recebe apenas os recortes das linhas reconhecidas.</p>
      </div>
      <form className="grade-form" onSubmit={event => { event.preventDefault(); void grade.submit(); }}>
        <div className="grade-file">
          <label htmlFor="grade-file" className="grade-file-button"><FileUp size={19} />{grade.file ? 'Trocar arquivo' : 'Escolher PDF ou imagem'}</label>
          <input id="grade-file" type="file" accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg" className="sr-only" disabled={grade.pending}
            onChange={event => { grade.choose(event.target.files?.[0] ?? null); event.target.value = ''; }} />
          {grade.file ? <p className="grade-file-name"><strong>{grade.file.name}</strong><span>{sizeLabel(grade.file.size)}</span>
            <button type="button" className="icon-button" aria-label="Remover arquivo" onClick={grade.clear} disabled={grade.pending}><X size={18} /></button></p>
            : <p className="grade-file-hint">PDF, PNG ou JPEG, até 8 MB.</p>}
        </div>
        {grade.file && <ImportacaoComprovante arquivo={grade.file} fase={fase}
          turmas={grade.outcome?.status === 'ok' ? grade.outcome.result.classes.length : undefined} />}
        <label htmlFor="grade-question" className="grade-label">Pergunta sobre a grade <span>(opcional)</span></label>
        <textarea id="grade-question" value={grade.question} onChange={event => grade.setQuestion(event.target.value)} maxLength={1200} rows={2}
          placeholder="Ex.: Quais aulas tenho na quarta e onde ficam as salas?" disabled={grade.pending} />
        <div className="grade-actions">
          {grade.pending ? <LiquidButton key="cancel" type="button" className="primary-button grade-submit" onClick={grade.cancel}><Square size={15} fill="currentColor" />Parar de aguardar</LiquidButton>
            : <LiquidButton key="submit" type="submit" className="primary-button grade-submit" disabled={!grade.file}>Ler comprovante</LiquidButton>}
        </div>
      </form>
      <p className="composer-note">{note}</p>
      <div role="status" aria-live="polite">
        {grade.outcome?.status === 'unavailable' && <div className="chat-connection grade-error"><p>{grade.outcome.message}</p>
          <button className="text-button" onClick={() => void grade.submit()}>Tentar novamente</button></div>}
      </div>
      {grade.outcome?.status === 'ok' && <Result result={grade.outcome.result} />}
    </div></div>
  </section>;
}

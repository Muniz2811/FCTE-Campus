import { useCallback, useEffect, useRef, useState } from 'react';
import type { GradeOutcome } from '../application/grade';
import { gradeReader } from '../infrastructure/http-grade';

export function useGrade() {
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState('');
  const [outcome, setOutcome] = useState<GradeOutcome | null>(null);
  const [pending, setPending] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  const choose = useCallback((next: File | null) => { setFile(next); setOutcome(null); }, []);
  const submit = useCallback(async () => {
    if (!file || request.current) return;
    setPending(true); setOutcome(null);
    const controller = new AbortController(); request.current = controller;
    try {
      const result = await gradeReader.read(file, question, controller.signal);
      if (!controller.signal.aborted) setOutcome(result);
    } catch { /* Cancelar não gera um resultado. */ }
    finally { if (request.current === controller) { request.current = null; setPending(false); } }
  }, [file, question]);
  const cancel = useCallback(() => { request.current?.abort(); request.current = null; setPending(false); }, []);
  const clear = useCallback(() => { cancel(); setFile(null); setQuestion(''); setOutcome(null); }, [cancel]);
  return { file, choose, question, setQuestion, outcome, pending, submit, cancel, clear };
}

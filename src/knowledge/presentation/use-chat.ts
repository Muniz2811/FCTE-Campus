import { useCallback, useEffect, useRef, useState } from 'react';
import type { AssistantHealth, KnowledgeResult } from '../application/assistant';
import { campusAssistant, getAssistantHealth } from '../infrastructure/http-assistant';

export type ChatMessage = { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; question: string; result: KnowledgeResult };
export function useChat(active: boolean) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [health, setHealth] = useState<AssistantHealth>({ status: 'idle' });
  const [pending, setPending] = useState(false);
  const request = useRef<AbortController | null>(null);
  const healthRequest = useRef<AbortController | null>(null);
  const previousRequest = useRef<string | undefined>(undefined);
  const refresh = useCallback(async () => {
    healthRequest.current?.abort();
    const controller = new AbortController(); healthRequest.current = controller;
    const timer = setTimeout(() => controller.abort(), 8000);
    setHealth({ status: 'loading' });
    const result = await getAssistantHealth(controller.signal);
    clearTimeout(timer);
    if (healthRequest.current === controller) setHealth(result);
  }, []);
  useEffect(() => { if (active) void refresh(); }, [active, refresh]);
  useEffect(() => () => { request.current?.abort(); healthRequest.current?.abort(); }, []);

  const send = useCallback(async (text: string) => {
    const question = text.trim();
    if (!question || request.current) return;
    setMessages(values => [...values, { id: crypto.randomUUID(), role: 'user', text: question }]);
    setPending(true);
    const controller = new AbortController(); request.current = controller;
    try {
      const result = await campusAssistant.ask({ text: question, campus: 'gama', previousRequestId: previousRequest.current }, controller.signal);
      if (!controller.signal.aborted) {
        if (result.requestId) previousRequest.current = result.requestId;
        setMessages(values => [...values, { id: crypto.randomUUID(), role: 'assistant', question, result }]);
      }
    } catch { /* Cancelar não cria uma resposta do assistente. */ }
    finally { if (request.current === controller) { request.current = null; setPending(false); } }
  }, []);
  const cancel = () => { request.current?.abort(); request.current = null; setPending(false); };
  const clear = () => { cancel(); previousRequest.current = undefined; setMessages([]); setDraft(''); };
  return { messages, draft, setDraft, health, pending, send, cancel, clear, refresh };
}

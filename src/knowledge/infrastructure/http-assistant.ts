import type { AssistantHealth, CampusAssistant, KnowledgeMeta, KnowledgeResult, KnowledgeSource } from '../application/assistant';
const api = `${import.meta.env.BASE_URL}api/v1/`;
const offline = 'Não foi possível conectar ao assistente. Verifique a conexão e tente novamente.';
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object';

function source(value: unknown): KnowledgeSource {
  if (!record(value) || !['id', 'title', 'excerpt', 'version'].every(key => typeof value[key] === 'string' && String(value[key]).trim())) throw new Error('Fonte inválida');
  let url: string | undefined;
  if (typeof value.url === 'string') {
    const parsed = new URL(value.url);
    if (['https:', 'http:'].includes(parsed.protocol)) url = parsed.href;
  }
  return { id: String(value.id), title: String(value.title), excerpt: String(value.excerpt), version: String(value.version), url,
    section: typeof value.section === 'string' ? value.section : undefined,
    sourceId: typeof value.sourceId === 'string' ? value.sourceId : undefined,
    reviewedAt: typeof value.reviewedAt === 'string' ? value.reviewedAt : undefined,
    validUntil: typeof value.validUntil === 'string' ? value.validUntil : undefined,
    distance: typeof value.distance === 'number' && Number.isFinite(value.distance) ? value.distance : undefined,
    lexicalScore: typeof value.lexicalScore === 'number' && Number.isFinite(value.lexicalScore) ? value.lexicalScore : undefined };
}

function result(value: unknown): KnowledgeResult {
  if (!record(value)) throw new Error('Resposta inválida');
  const meta: KnowledgeMeta = { requestId: typeof value.requestId === 'string' ? value.requestId : undefined,
    model: typeof value.model === 'string' ? value.model : undefined,
    baseVersion: typeof value.baseVersion === 'string' ? value.baseVersion : undefined,
    retrievalProfile: typeof value.retrievalProfile === 'string' ? value.retrievalProfile : undefined,
    retrievalMethod: typeof value.retrievalMethod === 'string' ? value.retrievalMethod : undefined,
    retrieved: Array.isArray(value.retrieved) ? value.retrieved.map(source) : undefined };
  if (value.status === 'answered' && typeof value.answer === 'string' && value.answer.trim() && Array.isArray(value.sources) && value.sources.length) {
    return { ...meta, status: 'answered', answer: value.answer, sources: value.sources.map(source) };
  }
  if (value.status === 'insufficient' && typeof value.message === 'string' && value.message.trim()) return { ...meta, status: 'insufficient', message: value.message };
  throw new Error('Contrato inválido');
}

export function createHttpAssistant(fetcher: typeof fetch = fetch): CampusAssistant {
  return { availability: 'available', async ask(question, signal) {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal?.aborted) throw new DOMException('Cancelado', 'AbortError');
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 110000);
    try {
      const response = await fetcher(`${api}chat`, { method: 'POST', cache: 'no-store', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(question) });
      if (!response.ok) {
        const error: unknown = await response.json().catch(() => null);
        return { status: 'unavailable', message: record(error) && typeof error.detail === 'string' ? error.detail : offline };
      }
      return result(await response.json());
    } catch (error) {
      if (!timedOut && (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError'))) throw error;
      return { status: 'unavailable', message: timedOut ? 'A consulta demorou demais. A chamada anterior pode ter consumido cota; aguarde antes de tentar novamente.' : offline };
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
  } };
}

export const campusAssistant = createHttpAssistant();

export async function getAssistantHealth(signal: AbortSignal): Promise<AssistantHealth> {
  try {
    const response = await fetch(`${api}health`, { cache: 'no-store', signal });
    const data: unknown = await response.json();
    if (response.ok && record(data) && data.status === 'ready' && typeof data.generationConfigured === 'boolean'
      && typeof data.sources === 'number' && typeof data.chunks === 'number' && typeof data.model === 'string') {
      return { status: 'ready', generationConfigured: data.generationConfigured, sources: data.sources, chunks: data.chunks, model: data.model };
    }
  } catch { /* A interface mantém o estado de conexão explícito. */ }
  return { status: 'unavailable', message: offline };
}

import { GRADE_MAX_BYTES } from '../application/grade';
import type { GradeAnswerStatus, GradeCitation, GradeClass, GradeIssue, GradeOutcome, GradePlace, GradeReader, GradeResult } from '../application/grade';
const api = `${import.meta.env.BASE_URL}api/v1/`;
const offline = 'Não foi possível conectar ao assistente. Verifique a conexão e tente novamente.';
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object';
const text = (value: unknown) => typeof value === 'string' && value.trim() ? value : undefined;
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const days = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab'];
const answerStatuses = ['respondida', 'insuficiente', 'sem_pergunta', 'indisponivel'];

function issue(value: unknown): GradeIssue {
  if (!record(value) || !text(value.codigo) || !text(value.mensagem)) throw new Error('Pendência inválida');
  return { code: String(value.codigo), message: String(value.mensagem) };
}

function place(value: unknown): GradePlace {
  if (!record(value) || !text(value.textoOriginal) || !text(value.predio) || !record(value.fonte)
    || !text(value.fonte.identificador) || !text(value.fonte.versaoFonte)) throw new Error('Local inválido');
  return { text: String(value.textoOriginal), building: String(value.predio), floor: text(value.andar),
    environmentId: text(value.ambienteId), precision: value.precisao === 'ambiente' ? 'ambiente' : 'predio',
    sourceId: String(value.fonte.identificador), sourceTitle: text(value.fonte.titulo) ?? String(value.fonte.identificador),
    version: String(value.fonte.versaoFonte) };
}

function gradeClass(value: unknown): GradeClass {
  if (!record(value) || !text(value.codigoComponente)) throw new Error('Turma inválida');
  return { code: String(value.codigoComponente), name: text(value.nomeComponente),
    hours: typeof value.cargaHoraria === 'number' ? value.cargaHoraria : undefined,
    group: text(value.turma), status: text(value.situacaoOriginal), declaredPlace: text(value.localTextoOriginal),
    meetings: list(value.encontros).map(item => {
      if (!record(item) || !days.includes(String(item.dia)) || !text(item.inicio) || !text(item.fim)) throw new Error('Encontro inválido');
      return { day: item.dia as GradeClass['meetings'][number]['day'], start: String(item.inicio), end: String(item.fim) };
    }),
    places: list(value.localizacoes).map(place), issues: list(value.pendencias).map(issue) };
}

function citation(value: unknown): GradeCitation {
  if (!record(value) || typeof value.n !== 'number' || !['comprovante', 'base'].includes(String(value.origem))
    || !text(value.referencia) || !text(value.trecho)) throw new Error('Citação inválida');
  return { n: value.n, origin: value.origem as GradeCitation['origin'], reference: String(value.referencia),
    excerpt: String(value.trecho), version: text(value.versao) };
}

function result(value: unknown): GradeResult {
  if (!record(value) || !record(value.grade) || !answerStatuses.includes(String(value.respostaStatus))) throw new Error('Contrato inválido');
  const grade = value.grade;
  return { period: text(grade.semestre), origin: String(grade.origem), classes: list(grade.turmas).map(gradeClass),
    issues: list(grade.pendencias).map(issue), question: text(value.pergunta), answer: text(value.resposta),
    answerStatus: value.respostaStatus as GradeAnswerStatus, citations: list(value.citacoes).map(citation) };
}

// A leitura pode levar mais de um minuto quando o Gemini está sobrecarregado; o servidor tenta várias vezes.
const TIMEOUT_MS = 200_000;

export function createHttpGradeReader(fetcher: typeof fetch = fetch): GradeReader {
  return { async read(file, question, signal): Promise<GradeOutcome> {
    if (file.size > GRADE_MAX_BYTES) return { status: 'unavailable', message: 'O arquivo excede o limite de 8 MB.' };
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal?.aborted) throw new DOMException('Cancelado', 'AbortError');
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, TIMEOUT_MS);
    try {
      const body = new FormData();
      body.append('arquivo', file, file.name);
      if (question?.trim()) body.append('pergunta', question.trim());
      const response = await fetcher(`${api}grade/consultar`, { method: 'POST', cache: 'no-store', signal: controller.signal, body });
      if (!response.ok) {
        const error: unknown = await response.json().catch(() => null);
        return { status: 'unavailable', message: record(error) && typeof error.detail === 'string' ? error.detail : offline };
      }
      return { status: 'ok', result: result(await response.json()) };
    } catch (error) {
      if (!timedOut && (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError'))) throw error;
      return { status: 'unavailable', message: timedOut ? 'A leitura demorou demais. O serviço de IA pode estar sobrecarregado; tente novamente em alguns minutos.' : offline };
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
  } };
}

export const gradeReader = createHttpGradeReader();

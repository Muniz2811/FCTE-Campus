import { expect, it } from 'vitest';
import { createHttpGradeReader } from './http-grade';

const pdf = () => new File(['%PDF-1.4 exemplo'], 'comprovante.pdf', { type: 'application/pdf' });
const body = { grade: { semestre: '2099.1', origem: 'pdf_visual', pendencias: [], turmas: [{
  codigoComponente: 'FGA9001', nomeComponente: 'COMPONENTE UM', cargaHoraria: 60, turma: 'Turma 01', situacaoOriginal: 'AGUARDANDO PROCESSAMENTO',
  localTextoOriginal: 'FCTE - S10 / MOCAP', encontros: [{ dia: 'qua', inicio: '14:00', fim: '15:50' }],
  localizacoes: [
    { textoOriginal: 'S10', predio: 'UAC', andar: 'Superior', ambienteId: 'S-029', precisao: 'ambiente', fonte: { identificador: 'MAP-UAC-1', titulo: 'Mapa UAC', versaoFonte: 'v1' } },
    { textoOriginal: 'MOCAP', predio: 'UED', precisao: 'predio', fonte: { identificador: 'DOC-006', titulo: 'Laboratórios', versaoFonte: 'v1' } }],
  pendencias: [{ codigo: 'locais_sem_vinculo_com_encontros', mensagem: 'Dois locais sem vínculo com os encontros.' }] }] },
  pergunta: 'Onde é a aula de quarta?', resposta: 'Quarta, 14:00. [1]', respostaStatus: 'respondida',
  citacoes: [{ n: 1, origem: 'comprovante', referencia: 'FGA9001', trecho: 'FGA9001 ...', versao: '2099.1' }] };

it('envia o arquivo e a pergunta como multipart e converte o contrato', async () => {
  let sent: FormData | undefined; let url = '';
  const reader = createHttpGradeReader(async (input, init) => { url = String(input); sent = init?.body as FormData; return new Response(JSON.stringify(body)); });
  const outcome = await reader.read(pdf(), ' Onde é a aula de quarta? ');
  expect(url).toMatch(/api\/v1\/grade\/consultar$/);
  expect((sent!.get('arquivo') as File).name).toBe('comprovante.pdf');
  expect(sent!.get('pergunta')).toBe('Onde é a aula de quarta?');
  expect(outcome.status).toBe('ok');
  if (outcome.status !== 'ok') return;
  const [turma] = outcome.result.classes;
  expect(outcome.result.period).toBe('2099.1');
  expect(turma.meetings).toEqual([{ day: 'qua', start: '14:00', end: '15:50' }]);
  expect(turma.places.map(p => [p.text, p.building, p.floor])).toEqual([['S10', 'UAC', 'Superior'], ['MOCAP', 'UED', undefined]]);
  expect(outcome.result.citations[0]).toMatchObject({ origin: 'comprovante', reference: 'FGA9001' });
});

it('a pergunta é opcional e não é enviada em branco', async () => {
  let sent: FormData | undefined;
  const reader = createHttpGradeReader(async (_url, init) => { sent = init?.body as FormData; return new Response(JSON.stringify({ ...body, pergunta: null, resposta: null, respostaStatus: 'sem_pergunta', citacoes: [] })); });
  const outcome = await reader.read(pdf(), '   ');
  expect(sent!.has('pergunta')).toBe(false);
  expect(outcome.status === 'ok' && outcome.result.answerStatus).toBe('sem_pergunta');
});

it('recusa arquivo acima de 8 MB sem chamar o servidor', async () => {
  let called = false;
  const grande = new File([new Uint8Array(8 * 1024 * 1024 + 1)], 'grande.pdf');
  const outcome = await createHttpGradeReader(async () => { called = true; return new Response('{}'); }).read(grande, undefined);
  expect(called).toBe(false);
  expect(outcome).toEqual({ status: 'unavailable', message: 'O arquivo excede o limite de 8 MB.' });
});

it('usa a mensagem do servidor nos erros e indisponibilidade em falha de rede ou contrato', async () => {
  const erro = await createHttpGradeReader(async () => new Response(JSON.stringify({ detail: 'Envie uma imagem PNG/JPEG ou um PDF.' }), { status: 415 })).read(pdf(), undefined);
  expect(erro).toEqual({ status: 'unavailable', message: 'Envie uma imagem PNG/JPEG ou um PDF.' });
  expect((await createHttpGradeReader(async () => { throw new TypeError('network'); }).read(pdf(), undefined)).status).toBe('unavailable');
  expect((await createHttpGradeReader(async () => new Response(JSON.stringify({ grade: { turmas: [{}] }, respostaStatus: 'respondida' }))).read(pdf(), undefined)).status).toBe('unavailable');
});

it('não transforma cancelamento em resultado de erro', async () => {
  const reader = createHttpGradeReader(async () => { throw new DOMException('cancelado', 'AbortError'); });
  await expect(reader.read(pdf(), undefined)).rejects.toMatchObject({ name: 'AbortError' });
});

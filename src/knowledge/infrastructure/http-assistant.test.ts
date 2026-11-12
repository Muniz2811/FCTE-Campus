import { expect, it } from 'vitest';
import { createHttpAssistant } from './http-assistant';

const response = { status: 'answered', answer: 'A biblioteca tem mesas. [1]', sources: [
  { id: 'c_exemplo', title: 'Biblioteca', excerpt: 'Mesas.', url: 'https://exemplo.invalid', version: 'v1' },
] };

it('envia somente o contrato de pergunta e aceita fontes identificadas', async () => {
  let payload = '';
  const assistant = createHttpAssistant(async (_url, init) => { payload = String(init?.body); return new Response(JSON.stringify(response)); });
  expect((await assistant.ask({ text: 'Onde estudar?', campus: 'gama' })).status).toBe('answered');
  expect(JSON.parse(payload)).toEqual({ text: 'Onde estudar?', campus: 'gama' });
});

it('falha de rede ou contrato incompleto retorna indisponibilidade', async () => {
  expect((await createHttpAssistant(async () => { throw new TypeError('network'); }).ask({ text: 'UAC', campus: 'gama' })).status).toBe('unavailable');
  expect((await createHttpAssistant(async () => new Response(JSON.stringify({ status: 'answered', answer: 'Sem fonte' }))).ask({ text: 'UAC', campus: 'gama' })).status).toBe('unavailable');
});

it('não transforma cancelamento em resposta de erro', async () => {
  const assistant = createHttpAssistant(async () => { throw new DOMException('cancelado', 'AbortError'); });
  await expect(assistant.ask({ text: 'UAC', campus: 'gama' })).rejects.toMatchObject({ name: 'AbortError' });
});

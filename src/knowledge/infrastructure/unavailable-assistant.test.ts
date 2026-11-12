import { expect, it } from 'vitest';
import { campusAssistant } from './unavailable-assistant';
it('declara indisponibilidade sem fabricar resposta ou fontes', async () => {
  expect(campusAssistant.availability).toBe('unavailable');
  const result = await campusAssistant.ask({ text: 'Onde estudar?', campus: 'gama' });
  expect(result.status).toBe('unavailable');
  expect(result).not.toHaveProperty('sources');
});

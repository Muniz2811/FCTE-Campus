import type { CampusAssistant } from '../application/assistant';
export const campusAssistant: CampusAssistant = {
  availability: 'unavailable',
  async ask() {
    return { status: 'unavailable', message: 'O assistente do campus ainda está em preparação. Explore os locais no mapa enquanto conectamos as fontes.' };
  },
};

import type { AvatarDefinition } from 'open-bot-avatar';

/**
 * Livro aberto com marcador, desenhado para o open-bot-avatar.
 * Validado em modo estrito (rosto com 16,6 unidades de folga, sem degraus na silhueta).
 * O marcador é uma parte separada para girar com o livro e manter a leitura de "fonte citada".
 */
export const livro: AvatarDefinition = {
  version: 1,
  id: 'livro-fcte',
  name: 'Livro',
  body: {
    path: 'M10 33C10 29 12.5 26.5 16 25.5C29 21 41 22.5 50 30C59 22.5 71 21 84 25.5C87.5 26.5 90 29 90 33V78C90 80.5 88 81.5 85.5 81C73 78.5 59 79 50 86C41 79 27 78.5 14.5 81C12 81.5 10 80.5 10 78Z'
      + 'M62 25C61.5 21 62 15 63.5 12.5C64.5 11 66.5 10.5 68.5 11L71 11.5C73 12 74 13.5 74 15.5L73 26C73 27.5 72 28 70.5 28H63.5C62.5 28 62 27 62 25Z',
  },
  eyes: { x: 50, y: 53, spacing: 18, scale: 1.12 },
};

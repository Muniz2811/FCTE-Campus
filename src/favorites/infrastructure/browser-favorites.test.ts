import { expect, it } from 'vitest';
import { readFavorites, saveFavorites, type FavoritesStorage } from './browser-favorites';

const storage = (value: string | null): FavoritesStorage => ({ getItem: () => value, setItem: () => {} });
it('recupera apenas IDs conhecidos, únicos, do formato versionado', () => {
  expect(readFavorites(storage('{"version":1,"ids":["a","inexistente","a",12]}'), ['a']).ids).toEqual(['a']);
  expect(readFavorites(storage('{"version":2,"ids":["a"]}'), ['a']).ids).toEqual([]);
});
it('permanece utilizável com JSON inválido e armazenamento bloqueado', () => {
  expect(readFavorites(storage('{'), ['a']).ids).toEqual([]);
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  expect(readFavorites(blocked, ['a']).available).toBe(false);
  expect(saveFavorites(blocked, ['a'])).toBe(false);
  expect(saveFavorites(null, ['a'])).toBe(false);
});
it('persiste IDs com versão, sem dados de localização', () => {
  let saved = '';
  const adapter = { getItem: () => null, setItem: (_key: string, value: string) => { saved = value; } };
  expect(saveFavorites(adapter, ['a', 'a'])).toBe(true);
  expect(JSON.parse(saved)).toEqual({ version: 1, ids: ['a'] });
});

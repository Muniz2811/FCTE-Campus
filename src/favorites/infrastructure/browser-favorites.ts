export interface FavoritesStorage { getItem(key: string): string | null; setItem(key: string, value: string): void }
export interface FavoritesRead { ids: string[]; available: boolean }
const key = 'fcte-campus:favorites';
export function readFavorites(storage: FavoritesStorage | null, knownIds: readonly string[]): FavoritesRead {
  if (!storage) return { ids: [], available: false };
  let value: string | null;
  try { value = storage.getItem(key); } catch { return { ids: [], available: false }; }
  try {
    const data: unknown = value ? JSON.parse(value) : null;
    if (!data || typeof data !== 'object' || !('version' in data) || data.version !== 1 ||
      !('ids' in data) || !Array.isArray(data.ids)) return { ids: [], available: true };
    const known = new Set(knownIds);
    return { ids: [...new Set(data.ids.filter((id): id is string => typeof id === 'string' && known.has(id)))], available: true };
  } catch { return { ids: [], available: true }; }
}
export function saveFavorites(storage: FavoritesStorage | null, ids: readonly string[]): boolean {
  if (!storage) return false;
  try { storage.setItem(key, JSON.stringify({ version: 1, ids: [...new Set(ids)] })); return true; }
  catch { return false; }
}

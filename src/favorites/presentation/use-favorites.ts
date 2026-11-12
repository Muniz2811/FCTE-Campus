import { useCallback, useState } from 'react';
import { readFavorites, saveFavorites, type FavoritesStorage } from '../infrastructure/browser-favorites';
const browserStorage = (): FavoritesStorage | null => {
  try { return window.localStorage; } catch { return null; }
};
export function useFavorites(knownIds: readonly string[]) {
  const [initial] = useState(() => readFavorites(browserStorage(), knownIds));
  const [ids, setIds] = useState(initial.ids);
  const [warning, setWarning] = useState(!initial.available);
  const toggle = useCallback((id: string) => {
    if (!knownIds.includes(id)) return;
    // Escrita fora do updater: React StrictMode pode chamar updaters mais de uma vez.
    const next = ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id];
    setIds(next);
    setWarning(!saveFavorites(browserStorage(), next));
  }, [ids, knownIds]);
  return { ids, toggle, warning };
}

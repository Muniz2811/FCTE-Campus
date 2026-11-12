import { useCallback, useEffect, useMemo, useState } from 'react';
import { places } from '../campus/infrastructure/catalog';
import { searchPlaces } from '../campus/application/search-places';
import type { Category } from '../campus/domain/place';
import { useFavorites } from '../favorites/presentation/use-favorites';

export type AppView = 'explore' | 'saved' | 'assistant';
const knownIds = places.map(place => place.id);
const readSelection = () => {
  const id = new URLSearchParams(location.hash.slice(1)).get('place');
  return knownIds.includes(id ?? '') ? id : null;
};
export function useExplorer() {
  const [view, setView] = useState<AppView>('explore');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<Category | 'all'>('all');
  const [selectedId, setSelectedId] = useState<string | null>(readSelection);
  const [sheet, setSheet] = useState<'peek' | 'list' | 'full'>('list');
  const favorites = useFavorites(knownIds);
  const visiblePlaces = useMemo(() => searchPlaces(places, { query, category }), [query, category]);
  const selected = places.find(place => place.id === selectedId) ?? null;
  useEffect(() => {
    const onHash = () => {
      const id = readSelection();
      setSelectedId(id);
      if (!id) return;
      setView('explore'); setQuery(''); setCategory('all'); setSheet('list');
    };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('popstate', onHash);
    return () => { window.removeEventListener('hashchange', onHash); window.removeEventListener('popstate', onHash); };
  }, []);
  const select = useCallback((id: string) => {
    if (!knownIds.includes(id)) return;
    const alreadyOpen = readSelection() !== null;
    setSelectedId(id); setView('explore'); setSheet('list');
    // Uma seleção em outra aba deve continuar visível entre os marcadores.
    setQuery(''); setCategory('all');
    const url = `${location.pathname}${location.search}#place=${encodeURIComponent(id)}`;
    if (alreadyOpen) history.replaceState(history.state, '', url);
    else history.pushState({ fctePanel: true }, '', url);
  }, []);
  const closeDetails = useCallback(() => {
    setSelectedId(null);
    if (history.state?.fctePanel === true) history.back();
    else history.replaceState(null, '', `${location.pathname}${location.search}`);
  }, []);
  const navigate = (next: AppView) => { closeDetails(); setView(next); setSheet('list'); };
  const changeQuery = (value: string) => { closeDetails(); setView('explore'); setQuery(value); setSheet('full'); };
  const changeCategory = (value: Category | 'all') => { closeDetails(); setView('explore'); setCategory(value); };
  return { view, navigate, query, changeQuery, category, changeCategory, visiblePlaces,
    selected, select, closeDetails, sheet, setSheet, favorites };
}

import type { Category, Place } from '../domain/place';
export interface SearchCriteria { query: string; category: Category | 'all' }
const normalize = (text: string): string => text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('pt-BR');
export function searchPlaces(places: readonly Place[], criteria: SearchCriteria): Place[] {
  const terms = normalize(criteria.query.trim()).split(/\s+/).filter(Boolean);
  return places.filter(place => {
    if (criteria.category !== 'all' && place.category !== criteria.category) return false;
    const searchable = normalize(`${place.name} ${place.description} ${place.buildingId ?? ''} ${place.candidateBuildingId ?? ''}`);
    return terms.every(term => searchable.includes(term));
  });
}

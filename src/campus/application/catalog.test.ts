import { describe, expect, it } from 'vitest';
import { validatePlaces, type Place } from '../domain/place';
import { searchPlaces } from './search-places';

const place: Place = {
  id: 'MAP-001-P014', name: 'UAC - Unidade acadêmica', category: 'building',
  coordinate: { latitude: -15.989, longitude: -48.044 }, description: '',
  sourceId: 'MAP-001', sourceLabel: 'Mapeamento da equipe', eligibleForPilot: true,
  buildingId: 'BLD-UAC', candidateBuildingId: null,
};
describe('catálogo e recuperação local', () => {
  it('aceita um ponto e rejeita coordenadas inválidas ou IDs duplicados', () => {
    expect(() => validatePlaces([place])).not.toThrow();
    expect(() => validatePlaces([place, place])).toThrow(/duplicado/);
    for (const coordinate of [{ latitude: NaN, longitude: 0 }, { latitude: 91, longitude: 0 }, { latitude: 0, longitude: 181 }]) {
      expect(() => validatePlaces([{ ...place, coordinate }])).toThrow(/coordenada/i);
    }
  });
  it('encontra nomes por palavras, sem distinguir acentos ou caixa', () => {
    expect(searchPlaces([place], { query: 'ACADEMICA uac', category: 'all' })).toEqual([place]);
  });
  it('combina filtro e busca, sem inventar resultados', () => {
    expect(searchPlaces([place], { query: '', category: 'building' })).toEqual([place]);
    expect(searchPlaces([place], { query: 'UAC', category: 'outdoor' })).toEqual([]);
    expect(searchPlaces([place], { query: 'sala com tomada', category: 'all' })).toEqual([]);
  });
});

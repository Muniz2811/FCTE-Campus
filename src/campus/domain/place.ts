export type Category = 'building' | 'entrance' | 'outdoor' | 'parking' | 'laboratory' | 'service';
export interface Coordinate { latitude: number; longitude: number }
export interface Place {
  id: string;
  name: string;
  category: Category;
  coordinate: Coordinate;
  description: string;
  sourceId: string;
  sourceLabel: string;
  eligibleForPilot: boolean;
  buildingId: string | null;
  candidateBuildingId: string | null;
}
export const categories: Record<Category, string> = {
  building: 'Prédios', entrance: 'Entradas', outdoor: 'Ao ar livre',
  parking: 'Estacionamentos', laboratory: 'Laboratórios', service: 'Serviços',
};
export function validatePlaces(places: readonly Place[]): void {
  const ids = new Set<string>();
  for (const place of places) {
    if (!place.id.trim() || !place.name.trim()) throw new Error('Local sem identificação');
    if (ids.has(place.id)) throw new Error(`ID duplicado: ${place.id}`);
    ids.add(place.id);
    const { latitude, longitude } = place.coordinate;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) ||
      Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
      throw new Error(`Coordenada inválida: ${place.id}`);
    }
    if (!(place.category in categories)) throw new Error(`Categoria inválida: ${place.id}`);
  }
}

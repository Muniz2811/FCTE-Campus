import L from 'leaflet';
import type { Place } from '../domain/place';
// Os símbolos são constantes internas; nomes importados são inseridos como textContent.
const paths = {
  building: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h1m4 0h1M9 11h1m4 0h1M10 21v-6h4v6"/>',
  entrance: '<path d="M4 21h16M6 21V4l10-2v19M16 5h3v16M12 12h.01"/>',
  outdoor: '<path d="m8 3-5 8h3l-4 6h12l-4-6h3L8 3ZM8 17v4M16 4l5 8h-3l4 5h-7m3 0v4"/>',
  parking: '<circle cx="12" cy="12" r="9"/><path d="M9 17V7h4a3 3 0 0 1 0 6H9"/>',
  laboratory: '<path d="M9 3h6m-5 0v6l-6 9a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-6-9V3M7 15h10"/>',
  service: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
};
export const markerIcon = (place: Place, active: boolean) => L.divIcon({
  className: `campus-marker ${active ? 'campus-marker--active' : ''} campus-marker--${place.category}`,
  html: `<span class="marker-glyph"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[place.category]}</svg></span>`,
  iconSize: active ? [52, 52] : [38, 38], iconAnchor: active ? [26, 45] : [19, 34],
  tooltipAnchor: [0, active ? -44 : -32],
});

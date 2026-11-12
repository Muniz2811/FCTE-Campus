import { memo, useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { useReducedMotion } from 'motion/react';
import { LocateFixed, Maximize, Minus, Plus, RefreshCw, WifiOff } from 'lucide-react';
import type { Place } from '../domain/place';
import { places as fullCatalog } from '../infrastructure/catalog';
import { markerIcon } from './map-markers';
import { useLocation } from './use-location';

interface Props { places: readonly Place[]; selected: Place | null; onSelect(id: string): void; sheet: string }
const campusBounds = L.latLngBounds(fullCatalog.map(place => [place.coordinate.latitude, place.coordinate.longitude]));

export const CampusMap = memo(function CampusMap({ places, selected, onSelect, sheet }: Props) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const tiles = useRef<L.TileLayer | null>(null);
  const markers = useRef(new Map<string, L.Marker>());
  const onSelectRef = useRef(onSelect);
  const reduced = useReducedMotion();
  const [tileError, setTileError] = useState(false);
  const { location: gps, request } = useLocation();
  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    if (!element.current) return;
    const instance = L.map(element.current, {
      zoomControl: false, attributionControl: false, minZoom: 3, maxZoom: 19,
      zoomAnimation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    });
    map.current = instance;
    instance.fitBounds(campusBounds.pad(.25));
    const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, keepBuffer: 1,
    }).addTo(instance);
    tiles.current = tileLayer;
    tileLayer.on('tileerror', () => setTileError(true));
    const resize = new ResizeObserver(() => instance.invalidateSize({ animate: false }));
    resize.observe(element.current);
    const stopHidden = () => { if (document.hidden) instance.stop(); };
    document.addEventListener('visibilitychange', stopHidden);
    return () => {
      resize.disconnect(); document.removeEventListener('visibilitychange', stopHidden);
      instance.remove(); map.current = null; markers.current.clear();
    };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const layer = L.layerGroup().addTo(instance);
    const next = new Map<string, L.Marker>();
    for (const place of places) {
      const label = document.createElement('span'); label.textContent = place.name;
      const marker = L.marker([place.coordinate.latitude, place.coordinate.longitude], {
        icon: markerIcon(place, false), title: place.name, alt: place.name, keyboard: true,
      }).bindTooltip(label, { direction: 'top', className: 'place-tooltip' }).addTo(layer);
      marker.on('click', () => onSelectRef.current(place.id));
      const icon = marker.getElement();
      icon?.setAttribute('aria-label', `Ver local: ${place.name}`);
      next.set(place.id, marker);
    }
    markers.current = next;
    return () => { layer.remove(); next.clear(); };
  }, [places]);

  useEffect(() => {
    for (const place of places) {
      const marker = markers.current.get(place.id);
      const active = place.id === selected?.id;
      marker?.setIcon(markerIcon(place, active));
      marker?.getElement()?.setAttribute('aria-label', `Ver local: ${place.name}${active ? ', selecionado' : ''}`);
      marker?.getElement()?.setAttribute('aria-pressed', String(active));
      marker?.setZIndexOffset(active ? 1000 : 0);
      if (active) marker?.openTooltip(); else marker?.closeTooltip();
    }
    const instance = map.current;
    if (!instance || !selected) return;
    const point = L.latLng(selected.coordinate.latitude, selected.coordinate.longitude);
    const zoom = Math.max(instance.getZoom(), 18);
    const projected = instance.project(point, zoom);
    // Levanta o destino acima do painel móvel, sem deslocar o painel desktop.
    if (window.matchMedia('(max-width: 760px)').matches) projected.y += instance.getSize().y * (sheet === 'peek' ? .05 : .17);
    instance.stop();
    instance.setView(instance.unproject(projected, zoom), zoom, { animate: !reduced, duration: .55 });
  }, [selected, places, reduced, sheet]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || gps.status !== 'ready') return;
    const position: L.LatLngTuple = [gps.coordinate.latitude, gps.coordinate.longitude];
    const group = L.layerGroup([
      L.circle(position, { radius: gps.accuracy, color: '#1769db', fillOpacity: .08, weight: 1 }),
      L.circleMarker(position, { radius: 8, color: '#fff', weight: 3, fillColor: '#1769db', fillOpacity: 1 }).bindTooltip('Sua localização nesta consulta'),
    ]).addTo(instance);
    instance.setView(position, 18, { animate: !reduced });
    return () => { group.remove(); };
  }, [gps, reduced]);

  return <section className="map-stage" aria-label="Mapa interativo do campus Gama">
    <div ref={element} className="campus-map" />
    <div className="map-campus-label"><span className="live-dot" /><strong>UnB Gama</strong><span>Distrito Federal</span></div>
    <div className="map-controls">
      <div className="zoom-controls"><button aria-label="Ampliar mapa" onClick={() => map.current?.zoomIn()}><Plus /></button>
        <button aria-label="Reduzir mapa" onClick={() => map.current?.zoomOut()}><Minus /></button></div>
      <button aria-label="Ver todo o campus" title="Ver todo o campus" onClick={() => map.current?.fitBounds(campusBounds.pad(.25), { animate: !reduced })}><Maximize /></button>
      <button className={gps.status === 'ready' ? 'is-located' : ''} aria-label="Usar minha localização" title="Usar minha localização" disabled={gps.status === 'loading'} onClick={request}>
        <LocateFixed className={gps.status === 'loading' ? 'is-loading' : ''} /></button>
    </div>
    <div className="map-messages" aria-live="polite">
      {tileError && <div className="map-notice"><WifiOff size={17} /><span>Parte do mapa não carregou. Os locais continuam na lista.</span><button aria-label="Tentar carregar mapa novamente" onClick={() => { setTileError(false); tiles.current?.redraw(); }}><RefreshCw size={17} /></button></div>}
      {gps.status === 'error' && <p className="map-notice">{gps.message}</p>}
      {gps.status === 'ready' && <p className="map-notice">GPS consultado agora · precisão aproximada de {Math.round(gps.accuracy)} m. Sem rastreamento.</p>}
    </div>
    <div className="map-attribution"><a href="https://leafletjs.com" target="_blank" rel="noreferrer">Leaflet</a><span> | </span>
      © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a></div>
  </section>;
});

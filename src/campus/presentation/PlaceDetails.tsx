import { ArrowLeft, ArrowUpRight, Bookmark, Check, Copy, MapPin, ScanLine } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { categories, type Place } from '../domain/place';
import { catalogSource } from '../infrastructure/catalog';
import { PlaceIcon } from '../../design/PlaceIcon';

export function PlaceDetails({ place, saved, onBack, onFavorite, onMap }: {
  place: Place; saved: boolean; onBack(): void; onFavorite(): void; onMap(): void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [place.id]);
  const copy = async () => {
    try { await navigator.clipboard.writeText(location.href); setCopyState('copied'); }
    catch { setCopyState('failed'); }
    timer.current = setTimeout(() => setCopyState('idle'), 3500);
  };
  const external = `https://www.google.com/maps/search/?api=1&query=${place.coordinate.latitude},${place.coordinate.longitude}`;
  return <motion.div className="place-details" initial={{ opacity: 0, x: 15 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: .2 }}>
    <div className="details-toolbar"><button className="text-button" onClick={onBack}><ArrowLeft size={18} />Todos os locais</button>
      <button className="icon-button" aria-label="Copiar link deste local" onClick={copy}>{copyState === 'copied' ? <Check size={19} /> : <Copy size={19} />}</button></div>
    <div className={`detail-emblem detail-emblem--${place.category}`}><PlaceIcon category={place.category} size={39} /><span className="emblem-orbit" /></div>
    <span className="category-label">{categories[place.category]} no campus Gama</span>
    <h2 ref={heading} tabIndex={-1}>{place.name}</h2>
    <p className="detail-description">{place.description || 'Este ponto foi marcado pela equipe. Ainda não há uma descrição adicional deste local.'}</p>
    <div className="detail-actions"><button className="primary-button" onClick={onMap}><MapPin size={18} />Ver no mapa</button>
      <button className={`secondary-button ${saved ? 'is-saved' : ''}`} aria-pressed={saved} onClick={onFavorite}><Bookmark size={18} fill={saved ? 'currentColor' : 'none'} />{saved ? 'Salvo' : 'Salvar'}</button></div>
    <a className="external-map" href={external} target="_blank" rel="noreferrer">Abrir destino no Google Maps<ArrowUpRight size={17} /><span className="sr-only"> (nova aba)</span></a>
    <section className="detail-source"><h3><ScanLine size={17} />Sobre este registro</h3>
      <dl><div><dt>Origem</dt><dd>{place.sourceLabel}</dd></div>
        <div><dt>Referência</dt><dd>{place.id}</dd></div>
        <div><dt>Coordenadas</dt><dd>{place.coordinate.latitude.toFixed(6)}, {place.coordinate.longitude.toFixed(6)}</dd></div>
        <div><dt>Exportação da base</dt><dd>{new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo' }).format(new Date(catalogSource.exportDate))}</dd></div>
        {place.buildingId && <div><dt>Prédio associado</dt><dd>{place.buildingId}</dd></div>}
        {place.candidateBuildingId && <div><dt>Associação a conferir</dt><dd>{place.candidateBuildingId}</dd></div>}
      </dl>
      <p>Posição de referência. Acesso, andar, recursos e disponibilidade atual ainda precisam de confirmação.</p>
      {!place.eligibleForPilot && <p>Este registro fica fora do piloto de perguntas e respostas.{place.category === 'laboratory' ? ' A identificação do laboratório ainda precisa ser confirmada.' : ''}</p>}
    </section>
    <p className="copy-feedback" role="status">{copyState === 'copied' ? 'Link do local copiado.' : copyState === 'failed' ? 'Copie o endereço desta página para compartilhar o local.' : ''}</p>
  </motion.div>;
}

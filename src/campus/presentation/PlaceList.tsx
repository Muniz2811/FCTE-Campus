import { ArrowUpRight, Bookmark, MapPinned, SearchX } from 'lucide-react';
import { motion } from 'motion/react';
import { categories, type Place } from '../domain/place';
import { PlaceIcon } from '../../design/PlaceIcon';
interface Props {
  places: readonly Place[]; favoriteIds: readonly string[];
  onSelect(id: string): void; onFavorite(id: string): void;
  empty?: 'search' | 'saved'; onReset?(): void;
}
export function PlaceList({ places, favoriteIds, onSelect, onFavorite, empty = 'search', onReset }: Props) {
  if (!places.length) return <div className="empty-state">
    {empty === 'saved' ? <Bookmark size={34} /> : <SearchX size={34} />}
    <h2>{empty === 'saved' ? 'Seus lugares, por perto.' : 'Nenhum local encontrado'}</h2>
    <p>{empty === 'saved' ? 'Toque no marcador de favorito ao lado de um lugar para encontrá-lo aqui.' : 'Tente o nome de um prédio, uma entrada ou outra categoria.'}</p>
    {onReset && <button className="text-button" onClick={onReset}>{empty === 'saved' ? 'Explorar o campus' : 'Limpar busca e filtros'}</button>}
  </div>;
  return <ul className="place-list">{places.map(place => {
    const saved = favoriteIds.includes(place.id);
    return <motion.li key={place.id} layout="position" transition={{ type: 'spring', stiffness: 450, damping: 35 }}>
      <button className="place-row" data-place-id={place.id} onClick={() => onSelect(place.id)}>
        <span className={`place-icon place-icon--${place.category}`}><PlaceIcon category={place.category} /></span>
        <span className="place-row-copy"><strong>{place.name}</strong><small>{categories[place.category]}<span aria-hidden="true"> · </span>Campus Gama</small></span>
        <ArrowUpRight className="row-arrow" size={18} aria-hidden="true" />
      </button>
      <motion.button whileTap={{ scale: .84 }} className={`favorite-button ${saved ? 'is-saved' : ''}`} aria-label={`${saved ? 'Remover' : 'Salvar'} ${place.name} ${saved ? 'dos' : 'nos'} favoritos`} aria-pressed={saved} onClick={() => onFavorite(place.id)}><Bookmark size={19} fill={saved ? 'currentColor' : 'none'} /></motion.button>
    </motion.li>;
  })}</ul>;
}

export function CatalogNote() {
  return <div className="catalog-note"><MapPinned size={17} aria-hidden="true" /><p>Mapeamento da equipe.<br /><span>Estamos conhecendo cada canto.</span></p></div>;
}

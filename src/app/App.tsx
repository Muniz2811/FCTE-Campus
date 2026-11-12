import { lazy, Suspense, useCallback, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ArrowDown, ArrowUp, ChevronDown, Download, MapPin } from 'lucide-react';
import { Brand } from '../design/Brand';
import { SearchBar } from '../campus/presentation/SearchBar';
import { CategoryFilters } from '../campus/presentation/CategoryFilters';
import { CatalogNote, PlaceList } from '../campus/presentation/PlaceList';
import { PlaceDetails } from '../campus/presentation/PlaceDetails';
import { places } from '../campus/infrastructure/catalog';
import { AssistantPanel } from '../knowledge/presentation/AssistantPanel';
import { useChat } from '../knowledge/presentation/use-chat';
import { useExplorer } from './use-explorer';
import { Navigation } from './Navigation';
import { AppStatus } from '../installation/AppStatus';
import { InstallDialog } from '../installation/InstallDialog';
import { useInstallation } from '../installation/use-installation';

const CampusMap = lazy(() => import('../campus/presentation/CampusMap').then(module => ({ default: module.CampusMap })));

export function App() {
  const explorer = useExplorer();
  const installation = useInstallation();
  const panel = useRef<HTMLDivElement>(null);
  const { selected, view, sheet, favorites } = explorer;
  const chat = useChat(view === 'assistant');
  const previousSelection = useRef<string | null>(null);
  const selectionOrigin = useRef<HTMLElement | null>(null);
  const restoreSelection = useRef<string | null>(null);
  const selectPlace = useCallback((id: string) => {
    selectionOrigin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    explorer.select(id);
  }, [explorer.select]);
  useEffect(() => {
    if (previousSelection.current && !selected) restoreSelection.current = previousSelection.current;
    previousSelection.current = selected?.id ?? null;
  }, [selected]);
  useEffect(() => { panel.current?.scrollTo({ top: 0 }); }, [selected?.id, view]);
  const afterPanelExit = () => {
    panel.current?.scrollTo({ top: 0 });
    if (!restoreSelection.current || selected) return;
    const id = restoreSelection.current;
    restoreSelection.current = null;
    if (view === 'explore') {
      requestAnimationFrame(() => {
        // Aguarda a lista entrar e preserva quem está digitando ou navegando nas abas.
        if (document.activeElement?.matches('input, textarea') || document.activeElement?.closest('.navigation')) return;
        const origin = selectionOrigin.current;
        const row = panel.current?.querySelector<HTMLButtonElement>(`[data-place-id="${id}"]`);
        const target = origin?.isConnected ? origin : row ?? document.querySelector<HTMLInputElement>('#campus-search');
        target?.focus();
      });
    }
  };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement).tagName;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || installation.open) return;
      if (event.key === '/') { event.preventDefault(); document.querySelector<HTMLInputElement>('#campus-search')?.focus(); }
      if (event.key === 'Escape') {
        if (selected) explorer.closeDetails(); else if (view !== 'assistant') explorer.setSheet('peek');
      }
    };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, [selected, view, installation.open, explorer.closeDetails, explorer.setSheet]);
  const reset = () => { explorer.changeQuery(''); explorer.changeCategory('all'); };
  const savedPlaces = places.filter(place => favorites.ids.includes(place.id));
  return <main className={`app-shell app-view--${view} sheet--${sheet}`}>
    <a href="#places-panel" className="skip-link" onClick={event => { event.preventDefault(); document.getElementById('places-panel')?.focus(); }}>Ir para a lista de locais</a>
    <Navigation view={view} onNavigate={explorer.navigate} onInstall={() => installation.setOpen(true)} />
    <header className="explorer-header"><div className="header-brand"><Brand />
      <button className="mobile-install icon-button" aria-label="Instalar aplicativo" onClick={() => installation.setOpen(true)}><Download size={20} /></button>
      <span className="campus-tag">Campus Gama<ChevronDown size={13} /></span></div>
      <SearchBar value={explorer.query} onChange={explorer.changeQuery} />
      <CategoryFilters value={explorer.category} onChange={explorer.changeCategory} />
    </header>
    <Suspense fallback={<section className="map-stage map-loading" aria-label="Carregando mapa"><MapPin size={26} /><p>Abrindo o campus…</p></section>}>
      <CampusMap places={explorer.visiblePlaces} selected={selected} onSelect={selectPlace} sheet={sheet} />
    </Suspense>
    <aside className="places-panel" id="places-panel" aria-label={view === 'saved' ? 'Locais salvos' : view === 'assistant' ? 'Assistente do campus' : 'Locais do campus'} tabIndex={-1}>
      <div className="sheet-handle"><span aria-hidden="true" /><button aria-label={sheet === 'full' ? 'Recolher painel' : 'Expandir painel'} onClick={() => explorer.setSheet(sheet === 'full' ? 'list' : 'full')}>{sheet === 'full' ? <ArrowDown size={17} /> : <ArrowUp size={17} />}</button></div>
      <button className="peek-summary" onClick={() => explorer.setSheet('list')}><strong>{selected?.name ?? (view === 'saved' ? 'Seus lugares salvos' : view === 'assistant' ? 'Assistente do campus' : 'Descubra o campus')}</strong><span>Ver detalhes <ArrowUp size={15} /></span></button>
      <div className="panel-scroll" ref={panel}>
        <AnimatePresence mode="wait" initial={false} onExitComplete={afterPanelExit}>
          {selected ? <PlaceDetails key={selected.id} place={selected} saved={favorites.ids.includes(selected.id)} onBack={explorer.closeDetails} onFavorite={() => favorites.toggle(selected.id)} onMap={() => { explorer.setSheet('peek'); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.peek-summary')?.focus()); }} />
            : <motion.div className={`panel-view panel-view--${view}`} key={view} initial={{ opacity: 0, y: 9 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18 }}>
              {view === 'assistant' ? <AssistantPanel chat={chat} /> : <>
                <div className="panel-heading"><div><h1>{view === 'saved' ? 'Seus lugares salvos' : explorer.query ? 'Resultado da busca' : 'Descubra o campus'}</h1>
                  <p>{view === 'saved' ? 'Um atalho para os seus próximos caminhos.' : 'Entre prédios, encontros e descobertas.'}</p></div>
                  <span className="count-badge" aria-label={`${view === 'saved' ? savedPlaces.length : explorer.visiblePlaces.length} locais`}>{view === 'saved' ? savedPlaces.length : explorer.visiblePlaces.length}</span></div>
                <div className="list-subheading"><span>{view === 'saved' ? 'Salvos neste dispositivo' : 'Locais mapeados'}</span><span><MapPin size={12} /> Gama, DF</span></div>
                <PlaceList places={view === 'saved' ? savedPlaces : explorer.visiblePlaces} favoriteIds={favorites.ids} onSelect={selectPlace} onFavorite={favorites.toggle} empty={view === 'saved' ? 'saved' : 'search'} onReset={view === 'saved' ? () => explorer.navigate('explore') : reset} />
                <CatalogNote />
              </>}
            </motion.div>}
        </AnimatePresence>
        {favorites.warning && <p className="storage-warning" role="status">O navegador bloqueou o armazenamento. Seus favoritos podem desaparecer ao fechar esta página.</p>}
      </div>
      <footer className="panel-footer"><span className="live-dot" /><span>Feito para explorar a FCTE</span><strong>Grupo 09</strong></footer>
      <AppStatus />
    </aside>
    <InstallDialog installation={installation} />
  </main>;
}

import { Bookmark, Compass, MessageCircle } from 'lucide-react';
import { motion } from 'motion/react';
import type { AppView } from './use-explorer';
import { Brand } from '../design/Brand';
const items = [
  { id: 'explore', label: 'Explorar', icon: Compass },
  { id: 'saved', label: 'Salvos', icon: Bookmark },
  { id: 'assistant', label: 'Assistente', icon: MessageCircle },
] as const;
export function Navigation({ view, onNavigate, onInstall }: { view: AppView; onNavigate(view: AppView): void; onInstall(): void }) {
  return <nav className="navigation" aria-label="Navegação principal">
    <div className="rail-brand"><Brand compact /></div>
    <div className="navigation-items">{items.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? 'nav-active' : ''} aria-current={view === id ? 'page' : undefined} onClick={() => onNavigate(id)}>
      {view === id && <motion.span className="nav-selection" layoutId="navigation-selection" transition={{ type: 'spring', stiffness: 420, damping: 35 }} />}
      <Icon size={23} strokeWidth={view === id ? 2.2 : 1.7} /><span>{label}</span>
    </button>)}</div>
    <button className="rail-install" onClick={onInstall} aria-label="Instalar e saber mais sobre o aplicativo"><span>+</span><small>Instalar</small></button>
    <div className="rail-footer" aria-label="Grupo 09">G09</div>
  </nav>;
}

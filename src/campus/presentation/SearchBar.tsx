import { Search, X } from 'lucide-react';
import { useRef } from 'react';
export function SearchBar({ value, onChange }: { value: string; onChange(value: string): void }) {
  const input = useRef<HTMLInputElement>(null);
  return <div className="search-bar"><Search size={22} aria-hidden="true" />
    <input ref={input} id="campus-search" name="campus-search" type="search" autoComplete="off" aria-label="Buscar local no campus" placeholder="Aonde vamos no campus?" value={value} onChange={event => onChange(event.target.value)} />
    {value ? <button aria-label="Limpar busca" onClick={() => { onChange(''); input.current?.focus(); }}><X size={18} /></button> : <kbd aria-hidden="true">/</kbd>}
  </div>;
}

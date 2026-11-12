import type { Category } from '../domain/place';
import { categories } from '../domain/place';
import { PlaceIcon } from '../../design/PlaceIcon';
import { LayoutGrid } from 'lucide-react';
export function CategoryFilters({ value, onChange }: { value: Category | 'all'; onChange(value: Category | 'all'): void }) {
  return <div className="category-filters" aria-label="Filtrar locais por categoria" role="group">
    <button aria-pressed={value === 'all'} onClick={() => onChange('all')}><LayoutGrid size={16} />Todos</button>
    {(Object.keys(categories) as Category[]).map(category => <button key={category} aria-pressed={value === category} onClick={() => onChange(category)}>
      <PlaceIcon category={category} size={17} />{categories[category]}</button>)}
  </div>;
}

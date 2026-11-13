import { BookOpenText } from 'lucide-react';

export function Brand() {
  return <div className="brand">
    <span className="brand-symbol" aria-hidden="true"><BookOpenText size={25} strokeWidth={1.6} /></span>
    <span className="brand-wordmark"><strong>FCTE Campus</strong><small>Assistente com fontes</small></span>
  </div>;
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={`brand ${compact ? 'brand--compact' : ''}`}>
    <span className="brand-symbol" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none">
      <path d="M20 5v30M5 20h30" stroke="currentColor" strokeWidth="1.5" opacity=".5" />
      <circle cx="20" cy="20" r="10" stroke="currentColor" strokeWidth="1.5" />
      <path d="m24 11-2 11-11 7 7-11 6-7Z" fill="currentColor" />
      <circle cx="20" cy="20" r="2.5" fill="#003f7a" />
    </svg></span>
    {!compact && <span className="brand-wordmark"><strong>FCTE<span>campus</span></strong><small>UnB, bem aqui.</small></span>}
  </div>;
}

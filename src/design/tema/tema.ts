/**
 * Tema do app. Sem escolha salva, segue o sistema. A escolha vira data-tema no <html>,
 * e o CSS troca o color-scheme: como as cores usam light-dark(), todo o app acompanha.
 * O index.html aplica a escolha salva antes da primeira pintura, para não piscar.
 */
export type Tema = 'claro' | 'escuro';
const CHAVE = 'fcte-tema';
export const EVENTO_TEMA = 'fcte-tema';

export function temaSalvo(): Tema | null {
  try {
    const v = localStorage.getItem(CHAVE);
    return v === 'claro' || v === 'escuro' ? v : null;
  } catch { return null; }
}

export function temaEfetivo(): Tema {
  const salvo = document.documentElement.dataset.tema;
  if (salvo === 'claro' || salvo === 'escuro') return salvo;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro';
}

export function aplicarTema(tema: Tema) {
  document.documentElement.dataset.tema = tema;
  try { localStorage.setItem(CHAVE, tema); } catch { /* Sem armazenamento, vale só nesta visita. */ }
  window.dispatchEvent(new Event(EVENTO_TEMA));
}

/** Avisa quem desenha em canvas ou lê o fundo: muda com o sistema ou com a escolha manual. */
export function aoMudarTema(fn: () => void) {
  const mq = matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', fn);
  window.addEventListener(EVENTO_TEMA, fn);
  return () => { mq.removeEventListener('change', fn); window.removeEventListener(EVENTO_TEMA, fn); };
}

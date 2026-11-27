import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { aoMudarTema, aplicarTema, temaEfetivo, type Tema } from './tema';

/**
 * Alternador claro/escuro. O botão quadrado desliza no trilho; o ícone é uma matriz de pontos
 * que se desfaz e se recompõe (lua ↔ sol). A troca revela o tema novo em círculo a partir do
 * botão (View Transitions, ideia do animated-theme-toggler do Magic UI).
 */
const LADO = 30;
const PASSO = 3;

type Ponto = { x: number; y: number };
function forma(tema: Tema): Ponto[] {
  const pts: Ponto[] = [];
  const c = LADO / 2;
  for (let y = 1.5; y < LADO; y += PASSO) {
    for (let x = 1.5; x < LADO; x += PASSO) {
      const dx = x - c, dy = y - c, d = Math.hypot(dx, dy);
      if (tema === 'escuro') {
        // Lua: disco menos um disco deslocado.
        if (d <= 11 && Math.hypot(x - (c + 6), y - (c - 5)) > 7.2) pts.push({ x, y });
      } else {
        // Sol: miolo e oito raios.
        const ang = Math.atan2(dy, dx);
        const raio = Math.abs(((ang / (Math.PI / 4)) % 1 + 1) % 1 - .5) < .17;
        if (d <= 5.6 || (raio && d >= 8.5 && d <= 13.5)) pts.push({ x, y });
      }
    }
  }
  return pts;
}

export function AlternarTema({ className = '', variante = 'trilho' }: { className?: string; variante?: 'trilho' | 'linha' }) {
  const [tema, setTema] = useState<Tema>(() => temaEfetivo());
  const canvas = useRef<HTMLCanvasElement>(null);
  const botao = useRef<HTMLButtonElement>(null);
  const atual = useRef<Ponto[]>(forma(tema));
  const quadro = useRef(0);

  useEffect(() => aoMudarTema(() => setTema(temaEfetivo())), []);

  // Anima os pontos: espalham para fora e se juntam na forma nova.
  useEffect(() => {
    const cv = canvas.current;
    const ctx = cv?.getContext('2d');
    if (!cv || !ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = LADO * dpr; cv.height = LADO * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const de = atual.current;
    const para = forma(tema);
    const n = Math.max(de.length, para.length);
    const espalho = Array.from({ length: n }, () => ({ x: (Math.random() - .5) * 26, y: (Math.random() - .5) * 26 }));
    const reduzido = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const inicio = performance.now();
    const dur = reduzido ? 1 : 620;
    // Cor fixa por tema: ler do CSS no meio da transição devolvia a cor antiga.
    const cor = tema === 'escuro' ? '#e9edff' : '#5a3d08';
    const pintar = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / dur);
      const e = t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
      const meio = Math.sin(t * Math.PI);
      ctx.clearRect(0, 0, LADO, LADO);
      ctx.fillStyle = cor;
      for (let i = 0; i < n; i++) {
        const a = de[i % de.length], b = para[i % para.length];
        const x = a.x + (b.x - a.x) * e + espalho[i].x * meio;
        const y = a.y + (b.y - a.y) * e + espalho[i].y * meio;
        ctx.globalAlpha = i >= para.length ? 1 - e : i >= de.length ? e : 1;
        ctx.beginPath();
        ctx.arc(x, y, 1.25 - meio * .45, 0, Math.PI * 2);
        ctx.fill();
      }
      if (t < 1) quadro.current = requestAnimationFrame(pintar);
      else atual.current = para;
    };
    cancelAnimationFrame(quadro.current);
    quadro.current = requestAnimationFrame(pintar);
    return () => cancelAnimationFrame(quadro.current);
  }, [tema]);

  const alternar = () => {
    const novo: Tema = tema === 'escuro' ? 'claro' : 'escuro';
    const aplicar = () => { aplicarTema(novo); setTema(novo); };
    const doc = document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void>; finished: Promise<void> } };
    if (!doc.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) { aplicar(); return; }
    // A View Transition tira o :hover da página; se a sidebar estava aberta, fica aberta até o fim.
    const sidebar = botao.current!.closest<HTMLElement>('.workspace-sidebar');
    const segurar = !!sidebar && (sidebar.matches(':hover') || sidebar.matches(':has(:focus-visible)'));
    if (segurar) sidebar!.classList.add('manter-aberta');
    const r = botao.current!.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const raio = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const transicao = doc.startViewTransition(() => flushSync(aplicar));
    transicao.finished.finally(() => {
      if (!segurar) return;
      // O navegador só recalcula o :hover quando o mouse se mexe. A sidebar fica aberta até o
      // próximo movimento, e só recolhe se o cursor estiver de fato fora dela.
      const conferir = (e: PointerEvent) => {
        const b = sidebar!.getBoundingClientRect();
        const dentro = e.clientX >= b.left && e.clientX <= b.right && e.clientY >= b.top && e.clientY <= b.bottom;
        if (dentro && sidebar!.matches(':hover')) return;
        sidebar!.classList.remove('manter-aberta');
        window.removeEventListener('pointermove', conferir);
      };
      window.addEventListener('pointermove', conferir);
      // O teclado também libera: foco fora da sidebar.
      sidebar!.addEventListener('focusout', () => { if (!sidebar!.matches(':hover')) sidebar!.classList.remove('manter-aberta'); }, { once: true });
    }).catch(() => {});
    transicao.ready.then(() => {
      // Percentuais da caixa de referência: em telas com escala fracionária, px sai deslocado.
      const px = `${(x / innerWidth) * 100}%`, py = `${(y / innerHeight) * 100}%`;
      const rr = `${(raio / (Math.hypot(innerWidth, innerHeight) / Math.SQRT2)) * 100}%`;
      document.documentElement.animate({ clipPath: [`circle(0% at ${px} ${py})`, `circle(${rr} at ${px} ${py})`] },
        { duration: 560, easing: 'cubic-bezier(.65,0,.35,1)', pseudoElement: '::view-transition-new(root)' });
    }).catch(() => {});
  };

  // "linha": na sidebar, uma linha igual às da navegação (pastilha na coluna dos ícones + rótulo).
  // "trilho": no celular, o botão desliza num trilho.
  if (variante === 'linha') return <button ref={botao} type="button" className={`alternar-tema alternar-tema--linha ${className}`} data-tema={tema} onClick={alternar}
    role="switch" aria-checked={tema === 'escuro'} aria-label="Tema escuro">
    {/* key: a pastilha remonta a cada troca para repetir o empurrão lateral. */}
    <span className="alternar-tema-botao" key={tema}><canvas ref={canvas} aria-hidden="true" /></span>
    <span className="sidebar-label">{tema === 'escuro' ? 'Tema escuro' : 'Tema claro'}</span>
  </button>;
  return <button ref={botao} type="button" className={`alternar-tema ${className}`} data-tema={tema} onClick={alternar}
    role="switch" aria-checked={tema === 'escuro'} aria-label="Tema escuro">
    <span className="alternar-tema-botao"><canvas ref={canvas} aria-hidden="true" /></span>
  </button>;
}

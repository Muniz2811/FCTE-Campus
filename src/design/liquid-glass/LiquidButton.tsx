import { useEffect, useRef, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from 'react';

/**
 * Botão líquido (referência: Liquid-button-microinteraction-concept, "Book a call").
 *
 * O contorno é montado a cada quadro com peças que nunca quebram a forma:
 * - borda de cima e borda de baixo: curvas com um inchaço em sino perto do x do cursor,
 *   que vai a zero junto das pontas (as pontas continuam presas, sem degrau);
 * - pontas: arcos de círculo perfeitos; quando o cursor puxa uma ponta, o arco inteiro
 *   se desloca para fora, em vez de se deformar.
 * A massa escorre para o cursor: o lado voltado para ele incha e o oposto recolhe um pouco.
 * Saindo do botão, a borda mais próxima avança um pouco mais, como uma língua contida.
 * Tudo passa por molas subamortecidas; a pílula é recortada pelo caminho (clip-path).
 */
const MARGEM = 28;      // área extra em volta da pílula, para o contorno poder inchar
const ENGROSSA = 5;     // inchaço máximo com o cursor dentro (px)
const LINGUA = 7;       // avanço extra máximo com o cursor saindo (px)
const SOLTA = 44;       // a partir dessa distância da borda o botão volta ao normal (px)
const PASSO_CURVA = 3;  // resolução das bordas (px)

type Mola = { x: number; v: number };
const mola = (x = 0): Mola => ({ x, v: 0 });
const molar = (m: Mola, alvo: number, k = .13, amort = .76) => { m.v = (m.v + (alvo - m.x) * k) * amort; m.x += m.v; };
const f = (v: number) => v.toFixed(2);

export function LiquidButton({ children, className = '', style, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  const botao = useRef<HTMLButtonElement>(null);
  const corpo = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = botao.current, cp = corpo.current;
    if (!el || !cp || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    // Amplitudes (px): inchaço da borda de cima, da de baixo, e deslocamento de cada ponta.
    const cima = mola(), baixo = mola(), esq = mola(), dir = mola(), centroX = mola(), luzX = mola(), luzY = mola();
    let alvo = { cima: 0, baixo: 0, esq: 0, dir: 0, x: 0 };
    let cursor = { x: 0, y: 0 };
    let w = 1, h = 1, r = .5;
    let seguindo = false, quadro = 0;
    let ultimoCursor: PointerEvent | null = null;

    const medir = () => {
      const b = el.getBoundingClientRect();
      w = b.width; h = b.height;
      r = Math.min(h / 2, w / 2, parseFloat(getComputedStyle(el).getPropertyValue('--lb-raio-px')) || h / 2);
    };

    /** Caminho fechado: borda de cima, ponta direita, borda de baixo, ponta esquerda. */
    const desenhar = () => {
      const xl = r - Math.max(0, esq.x), xr = w - r + Math.max(0, dir.x);   // centros dos arcos
      const sigma = Math.max(h * .9, (w - 2 * r) * .32);
      const bx = Math.min(Math.max(centroX.x, r), w - r);
      // Sino centrado no cursor, multiplicado por um envelope que zera nas pontas.
      const inchaco = (x: number) => {
        const t = Math.min(1, Math.max(0, (x - xl) / Math.max(1, xr - xl)));
        // Expoente > 1: a curva chega às pontas com inclinação zero e emenda lisa no arco.
        return Math.exp(-((x - bx) ** 2) / (2 * sigma ** 2)) * Math.sin(Math.PI * t) ** 1.5;
      };
      const M = MARGEM;
      let d = `M${f(xl + M)},${f(M)}`;
      // Borda de cima, da esquerda para a direita (y menor = mais para fora).
      for (let x = xl + PASSO_CURVA; x < xr; x += PASSO_CURVA) d += `L${f(x + M)},${f(M - cima.x * inchaco(x))}`;
      d += `L${f(xr + M)},${f(M)}`;
      // Ponta direita: arco, reta vertical (se o raio for menor que meia altura) e arco.
      d += `A${f(r)},${f(r)} 0 0 1 ${f(xr + r + M)},${f(r + M)}`;
      if (h - 2 * r > .5) d += `L${f(xr + r + M)},${f(h - r + M)}`;
      d += `A${f(r)},${f(r)} 0 0 1 ${f(xr + M)},${f(h + M)}`;
      // Borda de baixo, da direita para a esquerda.
      for (let x = xr - PASSO_CURVA; x > xl; x -= PASSO_CURVA) d += `L${f(x + M)},${f(h + M + baixo.x * inchaco(x))}`;
      d += `L${f(xl + M)},${f(h + M)}`;
      // Ponta esquerda.
      d += `A${f(r)},${f(r)} 0 0 1 ${f(xl - r + M)},${f(h - r + M)}`;
      if (h - 2 * r > .5) d += `L${f(xl - r + M)},${f(r + M)}`;
      d += `A${f(r)},${f(r)} 0 0 1 ${f(xl + M)},${f(M)}Z`;
      return d;
    };

    const passo = () => {
      molar(cima, alvo.cima); molar(baixo, alvo.baixo); molar(esq, alvo.esq); molar(dir, alvo.dir);
      molar(centroX, Math.min(alvo.x, w), .16, .72);
      molar(luzX, cursor.x, .06, .82); molar(luzY, cursor.y, .06, .82);
      cp.style.clipPath = `path('${desenhar()}')`;
      el.style.setProperty('--ix', `${luzX.x + MARGEM}px`);
      el.style.setProperty('--iy', `${luzY.x + MARGEM}px`);
      const energia = [cima, baixo, esq, dir].reduce((s, m) => s + Math.abs(m.x) + Math.abs(m.v), 0);
      if (!seguindo && energia < .02) { cp.style.clipPath = ''; quadro = 0; return; }
      quadro = requestAnimationFrame(passo);
    };
    const acordar = () => { if (!quadro) quadro = requestAnimationFrame(passo); };

    const mover = (e: PointerEvent) => {
      ultimoCursor = e;
      const b = el.getBoundingClientRect();
      if (Math.abs(b.width - w) > 1 || Math.abs(b.height - h) > 1) medir();
      const x = e.clientX - b.left, y = e.clientY - b.top;
      // Distância até a pílula: eixo central (de r a w-r, na meia altura) menos a meia altura.
      const ex = Math.min(Math.max(x, r), w - r), ey = h / 2;
      let ux = x - ex, uy = y - ey;
      const dist = Math.hypot(ux, uy);
      const fora = dist - h / 2;   // > 0 fora, < 0 dentro (aproximação de pílula)
      if (fora > SOLTA) { soltar(); return; }
      if (dist > .001) { ux /= dist; uy /= dist; } else { ux = 0; uy = 0; }
      cursor = { x: Math.min(Math.max(x, 0), w), y: Math.min(Math.max(y, 0), h) };
      // Quanto o cursor está fora do centro: no meio, inchaço leve e uniforme; perto da borda,
      // a massa vai para o lado do cursor e o lado oposto recolhe.
      const foco = Math.min(1, dist / (h / 2));
      const uniforme = ENGROSSA * .3 * (1 - foco);
      const lado = (u: number) => ENGROSSA * foco * (u > 0 ? u : -.45 * -u);
      // Saindo: a borda mais próxima avança mais, até LINGUA.
      const extra = fora > 0 ? Math.min(LINGUA, 3 + fora * .35) : 0;
      alvo = {
        cima: uniforme + lado(-uy) + extra * Math.max(0, -uy),
        baixo: uniforme + lado(uy) + extra * Math.max(0, uy),
        esq: Math.max(0, lado(-ux)) * .8 + extra * Math.max(0, -ux),
        dir: Math.max(0, lado(ux)) * .8 + extra * Math.max(0, ux),
        x: cursor.x,
      };
      el.dataset.ativo = 'true';
      acordar();
    };
    const soltar = () => {
      seguindo = false;
      alvo = { ...alvo, cima: 0, baixo: 0, esq: 0, dir: 0 };
      delete el.dataset.ativo;
      window.removeEventListener('pointermove', mover);
      acordar();
    };
    const comecar = (e: PointerEvent) => {
      if (el.disabled) return;
      if (!seguindo) {
        seguindo = true;
        medir();
        const b = el.getBoundingClientRect();
        const x = Math.min(Math.max(e.clientX - b.left, 0), w), y = Math.min(Math.max(e.clientY - b.top, 0), h);
        centroX.x = x; luzX.x = x; luzY.x = y;
        window.addEventListener('pointermove', mover);
      }
      mover(e);
    };
    el.addEventListener('pointerenter', comecar);
    // O botão muda de tamanho (a sidebar abre e recolhe): o contorno é recalculado para a nova
    // largura. Quem desliga é a distância (SOLTA): ao recolher, o cursor fica longe e o botão solta.
    const ro = new ResizeObserver(() => {
      const b = el.getBoundingClientRect();
      if (Math.abs(b.width - w) < 1 && Math.abs(b.height - h) < 1) return;
      medir();
      if (seguindo && ultimoCursor) mover(ultimoCursor);
      if (quadro || seguindo) acordar();
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      el.removeEventListener('pointerenter', comecar);
      window.removeEventListener('pointermove', mover);
      cancelAnimationFrame(quadro);
    };
  }, []);

  return <button ref={botao} className={`liquid-button ${className}`} style={{ '--lb-margem': `${MARGEM}px`, ...style } as CSSProperties} {...rest}>
    <span className="liquid-button-forma" aria-hidden="true">
      <span className="liquid-button-corpo" ref={corpo}><span className="liquid-button-iris" /></span>
    </span>
    <span className="liquid-button-rotulo">{children}</span>
  </button>;
}

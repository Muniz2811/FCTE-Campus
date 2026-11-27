import { useEffect, useRef, type RefObject } from 'react';
import { aoMudarTema } from './tema/tema';

/**
 * Fundo do chat. Cada ponto é um trecho da base (214 no índice atual).
 * Boas-vindas: os pontos formam um anel em volta do mascote.
 * Conversa: o anel se abre num campo em espiral, o "mapa da base".
 * Consulta: uma varredura percorre o campo e os trechos mandam feixes ao livro.
 * Resposta: os trechos citados acendem e se ligam ao mascote por um instante.
 */
const TAU = Math.PI * 2;
const OURO = Math.PI * (3 - Math.sqrt(5));
const FAIXAS = 42;

type Cores = { aura: [string, string, string]; ponto: [number, number, number]; escuro: boolean };
type Faixa = { origem: number; v: number; vida: number; comp: number; hue: number };

function lerCores(el: HTMLElement): Cores {
  const sonda = document.createElement('span');
  sonda.style.display = 'none';
  el.appendChild(sonda);
  const cor = (v: string) => { sonda.style.color = `var(${v})`; return getComputedStyle(sonda).color; };
  const aura: [string, string, string] = [cor('--cena-aura-1'), cor('--cena-aura-2'), cor('--cena-aura-3')];
  const ponto = (cor('--cena-ponto').match(/[\d.]+/g) ?? ['230', '240', '255']).slice(0, 3).map(Number) as [number, number, number];
  sonda.style.color = 'var(--canvas)';
  const fundo = (getComputedStyle(sonda).color.match(/[\d.]+/g) ?? ['0', '0', '0']).map(Number);
  sonda.remove();
  return { aura, ponto, escuro: fundo[0] + fundo[1] + fundo[2] < 382 };
}
function comAlfa(cor: string, a: number) {
  const [r, g, b] = (cor.match(/[\d.]+/g) ?? ['0', '0', '0']).map(Number);
  return `rgb(${r} ${g} ${b} / ${a})`;
}
function brilho(ctx: CanvasRenderingContext2D, x: number, y: number, raio: number, cor: string) {
  if (!(raio > 0)) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, raio);
  // Some na própria cor: 'transparent' é preto transparente e acinzenta o meio do degradê.
  g.addColorStop(0, cor);
  g.addColorStop(.55, cor.replace(/\/\s*[\d.]+\)$/, m => `/ ${(parseFloat(m.slice(1)) * .35).toFixed(3)})`));
  g.addColorStop(1, cor.replace(/\/\s*[\d.]+\)$/, '/ 0)'));
  ctx.fillStyle = g;
  ctx.fillRect(x - raio, y - raio, raio * 2, raio * 2);
}
/** Liga um id de fonte a um ponto fixo do mapa. */
function indiceDe(id: string, n: number) {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return (h >>> 0) % n;
}
const suave = (t: number) => t * t * (3 - 2 * t);

export function CampusScene({ paused, focused, pending, pulso, ancora, destaques = [], total = 214 }: {
  paused: boolean; focused: boolean; pending: boolean; pulso: number; ancora: RefObject<HTMLElement | null>;
  destaques?: string[]; total?: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const estado = useRef({ t: 1.2, atividade: 0, onda: -1, ultimoPulso: pulso, mix: focused ? 1 : 0, linhas: 0 });
  const acesos = useRef<Set<number>>(new Set());
  const n = Math.max(60, Math.min(600, total));

  useEffect(() => {
    acesos.current = new Set(destaques.map(id => indiceDe(id, n)));
  }, [destaques, n]);
  useEffect(() => {
    if (pulso !== estado.current.ultimoPulso) { estado.current.ultimoPulso = pulso; estado.current.onda = 0; estado.current.linhas = 1; }
  }, [pulso]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d', { willReadFrequently: true });
    if (!canvas || !ctx || !host.current) return;
    const cena = estado.current;
    let cores = lerCores(host.current);
    let w = 0, h = 0, frame = 0, anterior = 0;
    const faixas: Faixa[] = Array.from({ length: FAIXAS }, () => ({ origem: 0, v: 0, vida: 1, comp: 0, hue: 0 }));
    const pontos = Array.from({ length: n }, (_, i) => ({ anel: i % 3, fase: (i * 2.3) % TAU, ang: i / n * TAU }));
    const xs = new Float32Array(n), ys = new Float32Array(n);
    const alvoMix = focused ? 1 : 0;

    const centro = () => {
      const a = ancora.current?.getBoundingClientRect();
      const c = canvas.getBoundingClientRect();
      if (!a || !a.width) return { x: w * .72, y: h * .45, r: Math.min(w, h) * .2 };
      return { x: a.left - c.left + a.width / 2, y: a.top - c.top + a.height / 2, r: a.width * .62 };
    };

    const pintar = (dt: number) => {
      ctx.clearRect(0, 0, w, h);
      const { x, y, r } = centro();
      const t = cena.t, at = cena.atividade, m = suave(cena.mix);
      const aditivo = cores.escuro ? 'lighter' : 'source-over';
      const estreito = w < 700;
      // Campo em espiral centrado no livro, na horizontal, e acima dele: os feixes da consulta
      // chegam de todos os lados por igual (antes o campo ficava à direita e quase tudo vinha de lá).
      const fx = estreito ? w * .5 : x, fy = h * .42;
      const raioCampo = Math.min(estreito ? w * .62 : w * .46, h * .58);

      // Aura: segue o mascote no anel e se espalha pelo campo na conversa.
      ctx.globalCompositeOperation = aditivo;
      const intensidade = ((cores.escuro ? .34 : .42) + at * .18) * (1 - m * .45);
      cores.aura.forEach((cor, i) => {
        const ang = t * (.18 + i * .07) + i * 2.1;
        const cx = x + (fx - x) * m, cy = y + (fy - y) * m;
        const alcance = r + (raioCampo * .7 - r) * m;
        brilho(ctx, cx + Math.cos(ang) * alcance * .9, cy + Math.sin(ang) * alcance * .55, alcance * (2.3 - i * .25), comAlfa(cor, intensidade));
      });

      const [pr, pg, pb] = cores.ponto;
      const cabeca = t * (.55 + at * 1.6);
      const varredura = t * 1.4;
      for (let i = 0; i < n; i++) {
        const s = pontos[i];
        // Anel
        const raioAnel = r * (1.18 + s.anel * .075) + Math.sin(t * 1.3 + s.fase) * r * .012 * (1 + at * 3);
        const angAnel = s.ang + t * .04 * (s.anel - 1);
        const ax = x + Math.cos(angAnel) * raioAnel, ay = y + Math.sin(angAnel) * raioAnel;
        // Campo (espiral de girassol), girando bem devagar
        const rr = raioCampo * Math.sqrt((i + .5) / n);
        const th = i * OURO + t * .015;
        const bx = fx + Math.cos(th) * rr, by = fy + Math.sin(th) * rr * .78;
        const px = ax + (bx - ax) * m, py = ay + (by - ay) * m;
        xs[i] = px; ys[i] = py;

        let dist = Math.abs(((angAnel - cabeca) % TAU + TAU) % TAU - Math.PI);
        dist = Math.PI - dist;
        const pertoAnel = Math.max(0, 1 - dist / .5) * (1 - m);
        let dv = Math.abs(((th - varredura) % TAU + TAU) % TAU - Math.PI);
        dv = Math.PI - dv;
        const pertoBusca = Math.max(0, 1 - dv / .35) * at * m;
        const aceso = acesos.current.has(i) ? m : 0;
        const realce = Math.max(pertoAnel, pertoBusca, aceso);
        const baseAlfa = (cores.escuro ? .22 : .3) * (1 - m * .1);
        const alfa = baseAlfa + .14 * Math.sin(t * 2 + s.fase) ** 2 * (1 - m * .6) + realce * .75;
        const tam = 1 + realce * (aceso ? 1.9 : 1.5);
        if (realce > .2) {
          ctx.globalCompositeOperation = aditivo;
          brilho(ctx, px, py, tam * (aceso ? 9 : 6), comAlfa(cores.aura[aceso ? 0 : 1], .4 * realce));
        }
        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = `rgb(${pr} ${pg} ${pb} / ${Math.min(1, alfa)})`;
        ctx.beginPath();
        ctx.arc(px, py, tam, 0, TAU);
        ctx.fill();
      }

      // Resposta: linhas dos trechos citados até o livro, que esmaecem.
      if (cena.linhas > 0 && acesos.current.size) {
        cena.linhas = Math.max(0, cena.linhas - dt * .4);
        ctx.globalCompositeOperation = aditivo;
        ctx.lineWidth = 1.2;
        for (const i of acesos.current) {
          const g = ctx.createLinearGradient(xs[i], ys[i], x, y);
          g.addColorStop(0, comAlfa(cores.aura[0], .7 * cena.linhas));
          g.addColorStop(1, comAlfa(cores.aura[0], 0));
          ctx.strokeStyle = g;
          ctx.beginPath(); ctx.moveTo(xs[i], ys[i]); ctx.lineTo(x, y); ctx.stroke();
        }
      }

      // Consulta: feixes saem dos trechos e chegam ao livro, com dispersão cromática.
      if (at > .02) {
        ctx.globalCompositeOperation = aditivo;
        brilho(ctx, x, y, r * 2.2 * at, comAlfa(cores.aura[2], .5 * at));
        const canais: Array<[string, number]> = cores.escuro
          ? [['255 70 90', 1.8], ['80 255 160', 0], ['90 140 255', -1.8]]
          : [['205 35 70', 1.4], ['15 140 80', 0], ['40 80 210', -1.4]];
        for (const f of faixas) {
          f.vida += dt * f.v;
          if (f.vida >= 1) {
            f.vida = 0; f.v = .5 + Math.random() * .7; f.comp = .12 + Math.random() * .18; f.hue = Math.random();
            // Origem: um trecho acima do livro (até 8 sorteios); feixes subindo de baixo ficam estranhos.
            let o = Math.floor(Math.random() * n);
            for (let k = 0; k < 8 && ys[o] > y - r * .25; k++) o = Math.floor(Math.random() * n);
            f.origem = o;
          }
          const ox = xs[f.origem], oy = ys[f.origem];
          const dx = x - ox, dy = y - oy, d = Math.hypot(dx, dy) || 1;
          const ux = dx / d, uy = dy / d;
          const p = f.vida ** 1.5;
          const hx = ox + dx * p, hy = oy + dy * p;
          const cauda = d * f.comp;
          const alfa = Math.min(1, Math.sin(f.vida * Math.PI) * at * (cores.escuro ? 1.1 : .8));
          ctx.lineWidth = cores.escuro ? 2 : 1.6;
          for (const [rgb, desvio] of canais) {
            const sx = -uy * desvio * (1 + f.hue), sy = ux * desvio * (1 + f.hue);
            const g = ctx.createLinearGradient(hx, hy, hx - ux * cauda, hy - uy * cauda);
            g.addColorStop(0, `rgb(${rgb} / ${alfa})`);
            g.addColorStop(1, `rgb(${rgb} / 0)`);
            ctx.strokeStyle = g;
            ctx.beginPath(); ctx.moveTo(hx + sx, hy + sy); ctx.lineTo(hx - ux * cauda + sx * 1.8, hy - uy * cauda + sy * 1.8); ctx.stroke();
          }
        }
      }

      // Resposta: uma onda sai do mascote.
      if (cena.onda >= 0) {
        cena.onda += dt * .9;
        const o = cena.onda;
        ctx.globalCompositeOperation = aditivo;
        // Na conversa o livro é gigante: a onda fica fina e discreta para não virar um anel pesado.
        ctx.strokeStyle = comAlfa(cores.aura[0], Math.max(0, (.55 - .3 * m) * (1 - o)));
        ctx.lineWidth = (2 + 10 * (1 - o)) * (1 - .7 * m);
        ctx.beginPath(); ctx.arc(x, y, r * (.7 + o * 1.6), 0, TAU); ctx.stroke();
        if (o >= 1) cena.onda = -1;
      }
      ctx.globalCompositeOperation = 'source-over';
    };

    const redimensionar = () => {
      w = canvas.clientWidth; h = canvas.clientHeight;
      if (!w || !h) return;
      const escala = Math.min(window.devicePixelRatio || 1, 1.5, 1800 / w, 1200 / h);
      canvas.width = Math.round(w * escala); canvas.height = Math.round(h * escala);
      ctx.setTransform(escala, 0, 0, escala, 0, 0);
      pintar(0);
    };
    const passo = (agora: number) => {
      if (!anterior) anterior = agora;
      const dt = Math.min(.05, (agora - anterior) / 1000);
      if (agora - anterior >= 16 && w && h) {
        cena.t += dt * (1 + cena.atividade * .8);
        cena.atividade += ((pending ? 1 : 0) - cena.atividade) * .06;
        cena.mix += (alvoMix - cena.mix) * .045;
        if (Math.abs(alvoMix - cena.mix) < .002) cena.mix = alvoMix;
        anterior = agora;
        pintar(dt);
        // Conversa aberta e nada em movimento: para até a próxima consulta.
        if (focused && !pending && cena.onda < 0 && cena.linhas <= 0 && cena.atividade < .01 && cena.mix === alvoMix) return;
      }
      frame = requestAnimationFrame(passo);
    };
    const animado = !paused || cena.mix !== alvoMix;
    const visibilidade = () => {
      cancelAnimationFrame(frame); anterior = 0;
      if (animado && !document.hidden) frame = requestAnimationFrame(passo);
      else { cena.mix = alvoMix; pintar(0); }
    };
    const trocarTema = () => { if (host.current) cores = lerCores(host.current); pintar(0); };
    const ro = new ResizeObserver(redimensionar);
    ro.observe(canvas);
    if (ancora.current) ro.observe(ancora.current);
    redimensionar();
    visibilidade();
    document.addEventListener('visibilitychange', visibilidade);
    const parar = aoMudarTema(() => requestAnimationFrame(trocarTema));
    return () => {
      ro.disconnect(); cancelAnimationFrame(frame);
      document.removeEventListener('visibilitychange', visibilidade);
      parar();
    };
  }, [paused, focused, pending, pulso, ancora, n]);

  return <div ref={host} className="campus-scene" aria-hidden="true"><canvas ref={canvasRef} /></div>;
}

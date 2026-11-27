import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { LoaderCircle } from 'lucide-react';
import { LiquidGlass } from '../liquid-glass/LiquidGlass';

/**
 * Palco de importação do comprovante (referência: 3D-Photo-Import-Concept).
 * 1. escolhido: o comprovante vira um cartão 3D flutuando, que inclina seguindo o cursor.
 * 2. lendo: o cartão se desfaz de baixo para cima; da linha de corte saem caracteres que viram
 *    fios de luz com dispersão cromática e caem numa poça de luz, onde fica a pílula de status.
 * 3. pronto: o cartão some num clarão e o palco recolhe; as turmas entram em seguida.
 * 4. erro: o cartão se recompõe.
 * Os caracteres são decorativos: nada do conteúdo do comprovante é lido no navegador.
 */
export type FaseImportacao = 'escolhido' | 'lendo' | 'pronto' | 'erro';

const GLIFOS = '0123456789ABCDEFGHJKLMNPRSTUVXZ:-/';
const MAX_PARTICULAS = 420;

type Particula = { x: number; y: number; vx: number; vy: number; idade: number; vida: number; ch: string; tom: number };

const tamanhoArquivo = (bytes: number) => bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

export function ImportacaoComprovante({ arquivo, fase, turmas }: { arquivo: File; fase: FaseImportacao; turmas?: number }) {
  const palco = useRef<HTMLDivElement>(null);
  const cartao = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const faseRef = useRef(fase);
  faseRef.current = fase;
  const [previa, setPrevia] = useState<string | null>(null);
  const [recolhido, setRecolhido] = useState(false);
  const imagem = arquivo.type.startsWith('image/');

  // Prévia local do print (o arquivo já está no navegador; nada é enviado para isso).
  useEffect(() => {
    if (!imagem) { setPrevia(null); return; }
    const url = URL.createObjectURL(arquivo);
    setPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [arquivo, imagem]);

  // Pronto: depois do clarão, o palco recolhe até ficar só a pílula.
  useEffect(() => {
    if (fase !== 'pronto') { setRecolhido(false); return; }
    const t = setTimeout(() => setRecolhido(true), 1300);
    return () => clearTimeout(t);
  }, [fase]);

  // Inclinação do cartão seguindo o cursor.
  useEffect(() => {
    const el = palco.current, c = cartao.current;
    if (!el || !c || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const mover = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const nx = (e.clientX - r.left) / r.width - .5, ny = (e.clientY - r.top) / r.height - .5;
      c.style.setProperty('--incl-y', `${nx * 16}deg`);
      c.style.setProperty('--incl-x', `${-ny * 12}deg`);
    };
    const sair = () => { c.style.setProperty('--incl-y', '0deg'); c.style.setProperty('--incl-x', '0deg'); };
    el.addEventListener('pointermove', mover);
    el.addEventListener('pointerleave', sair);
    return () => { el.removeEventListener('pointermove', mover); el.removeEventListener('pointerleave', sair); };
  }, []);

  // Dissolução e partículas.
  useEffect(() => {
    const el = palco.current, cv = canvas.current, c = cartao.current;
    const ctx = cv?.getContext('2d');
    if (!el || !cv || !ctx || !c) return;
    const reduzido = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let w = 0, h = 0, quadro = 0, anterior = 0, acumulo = 0;
    let corte = 0, clarao = 0, poca = .25;
    const particulas: Particula[] = [];
    const ro = new ResizeObserver(() => {
      w = el.clientWidth; h = el.clientHeight;
      const dpr = Math.min(1.5, devicePixelRatio || 1);
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    });
    ro.observe(el);

    const passo = (agora: number) => {
      const dt = Math.min(.05, anterior ? (agora - anterior) / 1000 : .016);
      anterior = agora;
      const f = faseRef.current;
      const pr = el.getBoundingClientRect(), cr = c.getBoundingClientRect();
      const topo = cr.top - pr.top, base = cr.bottom - pr.top, esq = cr.left - pr.left, dir = cr.right - pr.left;
      const pocaX = w / 2, pocaY = h - 46;

      // Linha de corte: sobe até ~82% e fica tremulando enquanto o backend lê.
      if (f === 'lendo') corte = corte < .82 ? corte + dt * .14 : .82 + .025 * Math.sin(agora / 180);
      else if (f === 'pronto') corte = Math.min(1, corte + dt * 1.4);
      else corte = Math.max(0, corte - dt * (f === 'erro' ? 1.1 : 3));
      if (f === 'pronto' && corte >= 1 && clarao === 0) clarao = 1;
      c.style.setProperty('--corte', `${(corte * 100).toFixed(2)}%`);

      // Novos caracteres na linha de corte.
      if (f === 'lendo' && !reduzido) {
        acumulo += dt * 170;
        while (acumulo > 1 && particulas.length < MAX_PARTICULAS) {
          acumulo -= 1;
          particulas.push({
            x: esq + Math.random() * (dir - esq), y: base - corte * (base - topo) + (Math.random() - .5) * 8,
            vx: (Math.random() - .5) * 30, vy: -20 - Math.random() * 30, idade: 0, vida: 1.1 + Math.random() * .8,
            ch: GLIFOS[Math.floor(Math.random() * GLIFOS.length)], tom: Math.random(),
          });
        }
      }

      ctx.clearRect(0, 0, w, h);
      // Poça de luz embaixo: acende com o que chega e com o clarão final.
      poca += ((f === 'lendo' ? .75 : f === 'pronto' ? .5 : .25) + clarao - poca) * Math.min(1, dt * 3);
      const g = ctx.createRadialGradient(pocaX, pocaY + 10, 0, pocaX, pocaY + 10, w * .55);
      g.addColorStop(0, `rgb(255 244 226 / ${Math.min(.95, .32 * poca + .5 * clarao)})`);
      g.addColorStop(.25, `rgb(255 214 170 / ${.16 * poca})`);
      g.addColorStop(.6, `rgb(150 160 255 / ${.07 * poca})`);
      g.addColorStop(1, 'rgb(150 160 255 / 0)');
      ctx.globalCompositeOperation = 'lighter';
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      clarao = Math.max(0, clarao - dt * .9);

      ctx.font = '600 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      ctx.textAlign = 'center';
      for (let i = particulas.length - 1; i >= 0; i--) {
        const p = particulas[i];
        p.idade += dt;
        const t = p.idade / p.vida;
        if (t >= 1 || p.y > pocaY + 8) { particulas.splice(i, 1); poca = Math.min(1.4, poca + .012); continue; }
        if (p.idade < .22) {
          // Primeiro o caractere, tremendo na linha de corte.
          ctx.fillStyle = `rgb(235 240 255 / ${.85 * (1 - p.idade / .22 * .4)})`;
          ctx.fillText(p.ch, p.x + (Math.random() - .5), p.y);
          p.vy += 40 * dt;
        } else {
          // Depois, um fio de luz que acelera e converge para a poça.
          p.vy += 430 * dt;
          p.vx += (pocaX - p.x) * 1.9 * dt;
          const vel = Math.hypot(p.vx, p.vy) || 1;
          const ux = p.vx / vel, uy = p.vy / vel;
          // Cauda longa: no vídeo os fios parecem mechas de luz, não gotas.
          const cauda = Math.min(170, vel * .19);
          const alfa = Math.sin(Math.PI * Math.min(1, t * 1.15)) * .85;
          ctx.lineWidth = 1.15;
          for (const [rgb, d] of [['255 80 110', 1.6], ['110 255 190', 0], ['100 150 255', -1.6]] as const) {
            const ox = -uy * d * (1 + p.tom), oy = ux * d * (1 + p.tom);
            const gr = ctx.createLinearGradient(p.x, p.y, p.x - ux * cauda, p.y - uy * cauda);
            gr.addColorStop(0, `rgb(${rgb} / ${alfa})`);
            gr.addColorStop(1, `rgb(${rgb} / 0)`);
            ctx.strokeStyle = gr;
            ctx.beginPath(); ctx.moveTo(p.x + ox, p.y + oy); ctx.lineTo(p.x - ux * cauda + ox, p.y - uy * cauda + oy); ctx.stroke();
          }
        }
        p.x += p.vx * dt; p.y += p.vy * dt;
      }
      ctx.globalCompositeOperation = 'source-over';

      const ocioso = f === 'escolhido' && corte === 0 && !particulas.length && clarao === 0 && Math.abs(poca - .25) < .01;
      quadro = ocioso || document.hidden ? 0 : requestAnimationFrame(passo);
      if (!quadro) anterior = 0;
    };
    const acordar = () => { if (!quadro) quadro = requestAnimationFrame(passo); };
    acordar();
    const t = setInterval(acordar, 400);
    return () => { ro.disconnect(); cancelAnimationFrame(quadro); clearInterval(t); };
  }, []);

  const status = fase === 'lendo' ? 'Lendo o comprovante'
    : fase === 'pronto' ? `${turmas ?? 0} ${turmas === 1 ? 'turma lida' : 'turmas lidas'}`
      : fase === 'erro' ? 'Não foi possível ler agora' : 'Pronto para ler';

  return <div ref={palco} className={`importacao ${recolhido ? 'is-recolhido' : ''}`} data-fase={fase}>
    <canvas ref={canvas} className="importacao-particulas" aria-hidden="true" />
    <div className="importacao-cena" aria-hidden="true">
      <div ref={cartao} className="importacao-cartao" style={{ '--corte': '0%' } as CSSProperties}>
        {previa ? <img src={previa} alt="" />
          : <div className="importacao-documento">
            <span className="importacao-sigaa">UnB · SIGAA</span>
            <strong>Comprovante de matrícula</strong>
            <span className="importacao-linhas"><i /><i /><i /><i /><i /><i /></span>
            <span className="importacao-arquivo">{arquivo.name}</span>
          </div>}
        <span className="importacao-faixa">{imagem ? 'PRINT' : 'PDF'}<small>{tamanhoArquivo(arquivo.size)}</small></span>
      </div>
    </div>
    <LiquidGlass className="importacao-status" raio={99} tom="escuro" refracao={false} role="status">
      {fase === 'lendo' && <LoaderCircle size={16} className="chat-spinner" aria-hidden="true" />}
      <span>{status}</span>
      {fase === 'lendo' && <small>pode levar mais de um minuto</small>}
    </LiquidGlass>
  </div>;
}

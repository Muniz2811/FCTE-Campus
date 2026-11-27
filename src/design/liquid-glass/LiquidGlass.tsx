import { createElement, useEffect, useId, useRef, useState, type AllHTMLAttributes, type CSSProperties, type ElementType, type Ref } from 'react';
import { DISPERSAO, deslocamentoPara, mapaDeslocamento } from './mapa';
import { lerFundo } from './amostra';
import { aoMudarTema, temaEfetivo } from '../tema/tema';

/**
 * Vidro líquido em 6 camadas:
 * 1. projeção (sombra), 2. desfoque + saturação + brilho do fundo,
 * 3. refração na borda com dispersão cromática (só em Chromium, que aceita url() no backdrop-filter),
 * 4. coloração com opacidade pela complexidade do fundo, 5. luz nas bordas, 6. texto com um pouco da cor do fundo.
 * O tom (claro/escuro) vem do brilho médio do fundo: abaixo de 0,5, vidro escuro com texto claro.
 */
type Tom = 'auto' | 'claro' | 'escuro';
type Props = AllHTMLAttributes<HTMLElement> & { as?: ElementType; raio?: number; tom?: Tom; refracao?: boolean; elRef?: Ref<HTMLElement> };

const suportaRefracao = typeof navigator !== 'undefined'
  && !!(navigator as Navigator & { userAgentData?: { brands?: Array<{ brand: string }> } }).userAgentData?.brands?.some(b => b.brand === 'Chromium');

function tomDoSistema(): 'claro' | 'escuro' {
  return typeof document === 'undefined' ? 'claro' : temaEfetivo();
}

export function LiquidGlass({ as = 'div', raio = 22, tom = 'auto', refracao = true, className = '', style, children, elRef, ...rest }: Props) {
  const el = useRef<HTMLElement | null>(null);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const [tamanho, setTamanho] = useState<{ w: number; h: number } | null>(null);
  const [leitura, setLeitura] = useState<{ tom: 'claro' | 'escuro'; alpha: number }>(() => ({ tom: tom === 'auto' ? tomDoSistema() : tom, alpha: .5 }));

  useEffect(() => {
    const alvo = el.current;
    if (!alvo) return;
    const ro = new ResizeObserver(([entrada]) => {
      const caixa = entrada.borderBoxSize?.[0];
      const w = Math.round(caixa ? caixa.inlineSize : alvo.offsetWidth);
      const h = Math.round(caixa ? caixa.blockSize : alvo.offsetHeight);
      setTamanho(t => (t && Math.abs(t.w - w) < 2 && Math.abs(t.h - h) < 2 ? t : { w, h }));
    });
    ro.observe(alvo);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const alvo = el.current;
    if (!alvo) return;
    const medir = () => {
      if (document.hidden) return;
      const { brilho, complexidade } = lerFundo(alvo);
      const proprio: 'claro' | 'escuro' = tom === 'auto' ? (brilho < .5 ? 'escuro' : 'claro') : tom;
      setLeitura(l => (l.tom === proprio && Math.abs(l.alpha - complexidade) < .05 ? l : { tom: proprio, alpha: complexidade }));
    };
    medir();
    const intervalo = window.setInterval(medir, 1500);
    // Depois da troca de tema, mede quando a nova pintura já estiver na tela.
    const parar = aoMudarTema(() => { requestAnimationFrame(() => requestAnimationFrame(medir)); window.setTimeout(medir, 650); });
    return () => { window.clearInterval(intervalo); parar(); };
  }, [tom]);

  const mapa = refracao && suportaRefracao && tamanho ? mapaDeslocamento(tamanho.w, tamanho.h, raio) : null;
  const filtro = mapa ? `url(#lg-${id}) ` : '';
  const desloc = tamanho ? deslocamentoPara(tamanho.w, tamanho.h) : 0;
  const estilo = { ...style, '--lg-raio': `${raio}px`, '--lg-mistura': leitura.alpha.toFixed(3), '--lg-refracao': filtro } as CSSProperties;

  return createElement(as, {
    ...rest,
    ref: (no: HTMLElement | null) => {
      el.current = no;
      if (typeof elRef === 'function') elRef(no);
      else if (elRef) (elRef as { current: HTMLElement | null }).current = no;
    },
    className: `liquid-glass ${mapa ? 'has-refraction' : ''} ${className}`.trim(),
    'data-tom': leitura.tom,
    style: estilo,
  }, <>
    {mapa && tamanho && <svg className="liquid-glass-defs" aria-hidden="true" focusable="false" width="0" height="0">
      <filter id={`lg-${id}`} x="0" y="0" width={tamanho.w} height={tamanho.h} filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
        <feImage href={mapa} x="0" y="0" width={tamanho.w} height={tamanho.h} preserveAspectRatio="none" result="mapa" />
        {/* O vermelho curva um pouco mais que o azul: dispersão cromática de ±15%. */}
        <feDisplacementMap in="SourceGraphic" in2="mapa" scale={desloc * (1 + DISPERSAO)} xChannelSelector="R" yChannelSelector="G" result="dr" />
        <feDisplacementMap in="SourceGraphic" in2="mapa" scale={desloc} xChannelSelector="R" yChannelSelector="G" result="dg" />
        <feDisplacementMap in="SourceGraphic" in2="mapa" scale={desloc * (1 - DISPERSAO)} xChannelSelector="R" yChannelSelector="G" result="db" />
        <feColorMatrix in="dr" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
        <feColorMatrix in="dg" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
        <feColorMatrix in="db" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
        <feBlend in="r" in2="g" mode="screen" result="rg" />
        <feBlend in="rg" in2="b" mode="screen" />
      </filter>
    </svg>}
    {children}
  </>);
}

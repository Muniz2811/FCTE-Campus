/**
 * Lê o fundo atrás de um vidro em vários pontos e devolve o brilho médio e a
 * complexidade (desvio entre os pontos). O fundo é a cena em canvas do campus
 * composta sobre a cor de fundo do painel; fora dela, só a cor de fundo.
 */
export type Leitura = { brilho: number; complexidade: number };

const PONTOS: Array<[number, number]> = [[.5, .5], [.18, .22], [.82, .22], [.18, .78], [.82, .78], [.5, .12], [.5, .88]];

function linear(c: number) {
  const v = c / 255;
  return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
}
function luminancia(r: number, g: number, b: number) {
  return .2126 * linear(r) + .7152 * linear(g) + .0722 * linear(b);
}
function corDeFundo(el: Element | null): [number, number, number] {
  for (let atual = el; atual; atual = atual.parentElement) {
    const texto = getComputedStyle(atual).backgroundColor;
    const m = texto.match(/[\d.]+/g);
    if (!m || m.length < 3) continue;
    // color-mix() volta como "color(srgb r g b / a)", com canais de 0 a 1; rgb() vem de 0 a 255.
    const escala = texto.startsWith('color(') ? 255 : 1;
    const alfa = m.length >= 4 ? Number(m[3]) : 1;
    if (alfa > .5) return [Number(m[0]) * escala, Number(m[1]) * escala, Number(m[2]) * escala];
  }
  const tema = document.documentElement.dataset.tema;
  const escuro = tema ? tema === 'escuro' : matchMedia('(prefers-color-scheme: dark)').matches;
  return escuro ? [16, 22, 30] : [244, 246, 248];
}

export function lerFundo(el: HTMLElement): Leitura {
  const rect = el.getBoundingClientRect();
  const base = corDeFundo(el.parentElement);
  const cena = document.querySelector<HTMLCanvasElement>('.campus-scene canvas');
  const ctx = cena?.getContext('2d', { willReadFrequently: true });
  const cenaRect = cena?.getBoundingClientRect();
  const valores = PONTOS.map(([fx, fy]) => {
    const x = rect.left + rect.width * fx;
    const y = rect.top + rect.height * fy;
    let [r, g, b] = base;
    if (cena && ctx && cenaRect && x >= cenaRect.left && x < cenaRect.right && y >= cenaRect.top && y < cenaRect.bottom) {
      const sx = Math.floor((x - cenaRect.left) * cena.width / cenaRect.width);
      const sy = Math.floor((y - cenaRect.top) * cena.height / cenaRect.height);
      try {
        const [pr, pg, pb, pa] = ctx.getImageData(sx, sy, 1, 1).data;
        const a = pa / 255;
        r = pr * a + r * (1 - a); g = pg * a + g * (1 - a); b = pb * a + b * (1 - a);
      } catch { /* Canvas indisponível: fica a cor de fundo. */ }
    }
    return luminancia(r, g, b);
  });
  const media = valores.reduce((s, v) => s + v, 0) / valores.length;
  const desvio = Math.sqrt(valores.reduce((s, v) => s + (v - media) ** 2, 0) / valores.length);
  // Brilho perceptual (L*) para o corte em 0,5 ficar no meio visual, não no meio físico.
  const brilho = media <= .008856 ? media * 9.033 : 1.16 * Math.cbrt(media) - .16;
  return { brilho, complexidade: Math.min(1, desvio * 6) };
}

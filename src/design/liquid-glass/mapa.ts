/**
 * Mapa de deslocamento da refração de borda (camada 3 do vidro).
 *
 * Canal R = deslocamento em x, canal G = em y, 128 = parado. Só a faixa da borda
 * desloca: quanto mais perto do contorno, mais forte (curva quadrática); o centro fica plano.
 * O vetor aponta para fora, então o fundo perto da borda parece puxado para dentro.
 */
export const BORDA_PX = 44;
export const DESLOCAMENTO = BORDA_PX * 1.1;
export const DISPERSAO = 0.15;

/**
 * Em elementos baixos (pílulas, chips) a borda de 44px cobriria tudo e o deslocamento puxaria
 * pixels de fora do vidro, que chegam pretos. Borda e deslocamento encolhem com o menor lado.
 */
export function bordaPara(largura: number, altura: number) {
  return Math.min(BORDA_PX, Math.min(largura, altura) * .32);
}
export function deslocamentoPara(largura: number, altura: number) {
  return bordaPara(largura, altura) * 1.1 * Math.min(1, Math.min(largura, altura) / 120);
}

const cache = new Map<string, string>();

/** Distância com sinal até um retângulo arredondado centrado na origem (negativa por dentro). */
function sdf(px: number, py: number, hw: number, hh: number, r: number) {
  const qx = Math.abs(px) - hw + r;
  const qy = Math.abs(py) - hh + r;
  const fora = Math.hypot(Math.max(qx, 0), Math.max(qy, 0));
  return fora + Math.min(Math.max(qx, qy), 0) - r;
}

export function mapaDeslocamento(largura: number, altura: number, raio: number): string | null {
  if (largura < 8 || altura < 8 || typeof document === 'undefined') return null;
  // Resolução reduzida: o feImage estica o mapa e o resultado continua suave.
  const escala = Math.min(1, 220 / Math.max(largura, altura));
  const w = Math.max(8, Math.round(largura * escala));
  const h = Math.max(8, Math.round(altura * escala));
  const chave = `${w}x${h}r${Math.round(raio * escala)}`;
  const pronto = cache.get(chave);
  if (pronto) return pronto;

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const img = ctx.createImageData(w, h);
  const hw = w / 2, hh = h / 2;
  const r = Math.min(raio * escala, hw, hh);
  const borda = Math.max(2, Math.min(bordaPara(largura, altura) * escala, hw, hh));
  const e = 0.6;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const px = x + .5 - hw, py = y + .5 - hh;
      const d = -sdf(px, py, hw, hh, r);
      let dx = 0, dy = 0;
      if (d >= 0 && d < borda) {
        // Normal para fora pelo gradiente do campo de distância.
        const gx = sdf(px + e, py, hw, hh, r) - sdf(px - e, py, hw, hh, r);
        const gy = sdf(px, py + e, hw, hh, r) - sdf(px, py - e, hw, hh, r);
        const n = Math.hypot(gx, gy) || 1;
        const forca = (1 - d / borda) ** 2;
        dx = (gx / n) * forca;
        dy = (gy / n) * forca;
      }
      const i = (y * w + x) * 4;
      img.data[i] = Math.round(128 + dx * 127);
      img.data[i + 1] = Math.round(128 + dy * 127);
      img.data[i + 2] = 128;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const url = canvas.toDataURL('image/png');
  if (cache.size > 40) cache.clear();
  cache.set(chave, url);
  return url;
}

import { renderAvatarSvg } from 'open-bot-avatar';
import { livro } from './livro';

// Pose fixa e lisa: aparece em cada resposta e na marca, então não usa canvas nem WebGL.
// O SVG é gerado pela biblioteca a partir da definição local, sem dado do usuário.
const svg = renderAvatarSvg(livro, { color: '#f2b705', eyeColor: '#1d1606', size: 64 });

export function MascoteMini({ tamanho = 22 }: { tamanho?: number }) {
  return <span className="mascote-mini" style={{ width: tamanho, height: tamanho }} aria-hidden="true" dangerouslySetInnerHTML={{ __html: svg }} />;
}

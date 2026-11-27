import { MascoteMini } from './mascote/MascoteMini';

export function Brand() {
  return <div className="brand">
    <span className="brand-symbol" aria-hidden="true"><MascoteMini tamanho={30} /></span>
    <span className="brand-wordmark"><strong>FCTE Campus</strong><small>Respostas com fonte</small></span>
  </div>;
}

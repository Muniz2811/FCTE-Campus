import { useEffect, useRef } from 'react';
import type { AvatarState, AvatarStateDefinition } from 'open-bot-avatar';
import { mountAvatar, type MountedAvatar } from 'open-bot-avatar/dom';
import { livro } from './livro';

export type MascoteEstado = 'idle' | 'thinking' | 'done' | 'waiting' | 'blocked' | 'feliz' | 'lendo';

/**
 * Estado próprio para a consulta com o livro gigante: ele balança devagar, aperta os olhos e
 * varre o olhar de um lado a outro, como quem lê linhas. Sem marca: o corpo continua inteiro.
 */
const lendo: AvatarStateDefinition = {
  id: 'lendo',
  pose: ctx => ({
    ...ctx.rest(1.15),
    roll: 2.5 * ctx.wave(2.8),
    lift: -1.2 + 1.2 * ctx.wave(1.4),
    gazeX: .65 * ctx.wave(1.9),
    gazeY: .35,
    squintL: .32,
    squintR: .32,
  }),
};

/**
 * O livro peludo do FCTE Campus. A pelagem (WebGL2) é carregada sob demanda;
 * sem WebGL2 o renderer desenha o livro liso, com os mesmos estados.
 */
export function Mascote({ estado, followPointer = true, className, olhar = null }: {
  estado: MascoteEstado; followPointer?: boolean; className?: string;
  /** Direção fixa do olhar (-1..1); null segue o cursor. */
  olhar?: { x: number; y: number } | null;
}) {
  const host = useRef<HTMLDivElement>(null);
  const avatar = useRef<MountedAvatar | null>(null);

  useEffect(() => {
    let vivo = true;
    avatar.current = mountAvatar(host.current!, {
      definition: livro,
      color: 'var(--mascote-pelo)',
      eyeColor: 'var(--mascote-olho)',
      depth: 8,
      label: '',
    });
    void import('open-bot-avatar/materials/fluffy').then(({ fluffy }) => {
      if (vivo) avatar.current?.update({ material: fluffy });
    }).catch(() => { /* Sem a pelagem, o livro continua liso. */ });
    return () => { vivo = false; avatar.current?.destroy(); avatar.current = null; };
  }, []);

  useEffect(() => {
    // 'feliz': corpo em repouso com olhos felizes, sem a marca de 'done'.
    const state: AvatarState | AvatarStateDefinition = estado === 'feliz' ? 'idle' : estado === 'lendo' ? lendo : estado;
    avatar.current?.update({ state, mood: estado === 'done' || estado === 'feliz' ? 'happy' : 'neutral', followPointer, lookAt: olhar });
  }, [estado, followPointer, olhar?.x, olhar?.y]);

  return <div ref={host} className={className} style={{ width: '100%', aspectRatio: '1' }} aria-hidden="true" />;
}

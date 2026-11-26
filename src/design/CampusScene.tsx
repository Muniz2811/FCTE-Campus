import { useEffect, useRef } from 'react';

const TAU = Math.PI * 2;
const VERTICES = 36;
const angles = Array.from({ length: VERTICES }, (_, i) => i * TAU / VERTICES);

function membrane(context: CanvasRenderingContext2D, radius: number, t: number, layer: number) {
  const points = angles.map(angle => {
    const ripple = 1 + .102 * Math.sin(3 * angle + t * 1.1 + layer)
      + .058 * Math.sin(5 * angle - t * 1.5)
      + .11 * Math.cos(2 * angle - t * .64 + layer);
    return [Math.cos(angle) * ripple * radius, Math.sin(angle) * ripple * radius * .82];
  });
  context.beginPath();
  const first = points[0];
  const last = points[VERTICES - 1];
  context.moveTo((last[0] + first[0]) / 2, (last[1] + first[1]) / 2);
  for (let i = 0; i < VERTICES; i++) {
    const [x, y] = points[i];
    const [nextX, nextY] = points[(i + 1) % VERTICES];
    const middleX = (x + nextX) / 2;
    const middleY = (y + nextY) / 2;
    context.quadraticCurveTo(x, y, middleX, middleY);
  }
  context.closePath();
}

function glow(context: CanvasRenderingContext2D, x: number, y: number, radius: number, color: string) {
  const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
  gradient.addColorStop(0, color);
  gradient.addColorStop(1, 'transparent');
  context.fillStyle = gradient;
  context.fillRect(x - radius, y - radius, 2 * radius, 2 * radius);
}

function draw(context: CanvasRenderingContext2D, width: number, height: number, t: number, activity: number) {
  context.clearRect(0, 0, width, height);
  const compact = width < 650;
  const base = Math.min(width * (compact ? .37 : .28), height * .41, 330);
  const pulse = (1 + Math.sin(t * TAU / 4 - .65)) / 2;
  const radius = base * (.81 + .23 * pulse + .15 * activity);
  context.save();
  context.translate(width * (compact ? .72 : .73) + Math.sin(t * .65) * base * .06,
    height * (compact ? .25 : .47) + Math.sin(t * 1.03) * base * .06);

  glow(context, 0, 0, base * 1.66, '#54777926');
  for (let i = 2; i >= 0; i--) {
    const size = radius * (1 + .13 * i);
    membrane(context, size, t, i * .8);
    const surface = context.createLinearGradient(-size, -size * .65, size, size * .8);
    surface.addColorStop(0, '#a2bdb645');
    surface.addColorStop(.27, '#4064653b');
    surface.addColorStop(.58, '#0d294723');
    surface.addColorStop(1, '#7fa59f50');
    context.fillStyle = surface;
    context.fill();
    context.lineWidth = i === 0 ? 1.4 : .8;
    context.strokeStyle = i === 0 ? '#99bab294' : '#8bafc04a';
    context.stroke();
  }

  context.save();
  membrane(context, radius, t, 0);
  context.clip();
  const core = context.createRadialGradient(0, 0, radius * .25, 0, 0, radius * 1.08);
  core.addColorStop(0, '#061827d0');
  core.addColorStop(.76, '#1037481a');
  core.addColorStop(1, '#9fbdb166');
  context.fillStyle = core;
  context.fillRect(-radius * 1.3, -radius * 1.3, radius * 2.6, radius * 2.6);
  glow(context, Math.cos(t * 1.18) * radius * .67, Math.sin(t * 1.18) * radius * .53, radius * .65, '#82aba45c');
  glow(context, Math.cos(t * .93 + 2.7) * radius * .56, Math.sin(t * .93 + 2.7) * radius * .59, radius * .6, '#6489a46e');
  glow(context, -radius * .6, -radius * .48, radius * .45, '#b1c9c88c');
  context.restore();

  const blink = Math.max(.17, 1 - Math.max(0, Math.sin(t * 1.58 - 1.2)) ** 38);
  const gaze = Math.sin(.91 * t) * radius * .09;
  for (const side of [-1, 1]) {
    const x = gaze + side * radius * .085;
    const y = Math.sin(t * 1.22) * radius * .055;
    glow(context, x, y, radius * .1, '#9bbab948');
    context.beginPath();
    context.ellipse(x, y, radius * .023, radius * .029 * blink, 0, 0, TAU);
    context.fillStyle = '#e3efea';
    context.fill();
  }
  context.restore();
}

export function CampusScene({ paused, focused, pending }: { paused: boolean; focused: boolean; pending: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneTime = useRef({ time: .9, activity: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    const scene = sceneTime.current;
    let width = 0;
    let height = 0;
    let frame = 0;
    let previous = 0;
    const animated = !paused && (!focused || pending);
    const paint = () => draw(context, width, height, scene.time, scene.activity);
    const resize = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      if (!width || !height) return;
      const scale = Math.min(window.devicePixelRatio || 1, 1.35, 1500 / width, 1000 / height);
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round(height * scale);
      context.setTransform(scale, 0, 0, scale, 0, 0);
      paint();
    };
    const tick = (now: number) => {
      if (!previous) previous = now;
      const elapsed = now - previous;
      if (elapsed >= 26 && width && height) {
        scene.time += Math.min(.064, elapsed / 1000) * (pending ? 1.55 : 1);
        scene.activity += ((pending ? 1 : 0) - scene.activity) * .075;
        previous = now;
        paint();
      }
      frame = requestAnimationFrame(tick);
    };
    const syncVisibility = () => {
      cancelAnimationFrame(frame);
      previous = 0;
      if (animated && !document.hidden) frame = requestAnimationFrame(tick);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    syncVisibility();
    document.addEventListener('visibilitychange', syncVisibility);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      document.removeEventListener('visibilitychange', syncVisibility);
    };
  }, [paused, focused, pending]);

  return <div className="campus-scene" aria-hidden="true"><canvas ref={canvasRef} /></div>;
}

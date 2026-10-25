// The "liquid pitch" backdrop, shared by every page: a canvas drawn in code (mowing stripes bent by a slow vortex and waves,
// cream highlights, a wavy horizon under a blue sky), plus a film-grain layer and a dimming layer for the inner pages.
// It animates on the landing page and stays a still frame elsewhere (saves battery while you read or watch a replay).
// Nothing is loaded: no images, fonts or requests.
const SKY = '#1D4E9E', CREAM = '#F4EFD8';
const prefersReduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Height of the wavy horizon (the edge between the blue sky and the lawn) at x. */
export const horizon = (x, h, t) => h * 0.27 + h * 0.03 * Math.sin(x * 0.0055 + t * 0.25) + h * 0.015 * Math.sin(x * 0.013 - t * 0.35);

/** Bend a lawn point: a slow vortex plus rolling waves, so straight mowing stripes flow like liquid. */
export function warp(x, y, w, h, t) {
  const cx = w * 0.62, cy = h * 0.68, R = w * 0.3;
  const dx = x - cx, dy = y - cy, ang = (2.1 + 0.25 * Math.sin(t * 0.3)) * Math.exp(-(dx * dx + dy * dy) / (2 * R * R));
  const c = Math.cos(ang), sn = Math.sin(ang);
  const nx = cx + dx * c - dy * sn;
  let ny = cy + dx * sn + dy * c;
  ny += h * 0.028 * Math.sin(nx * 0.006 + y * 0.01 + t * 0.4) + h * 0.012 * Math.sin(nx * 0.015 - t * 0.5);
  return [nx, ny];
}

export function paintFlow(ctx, w, h, t) {
  const step = Math.max(6, w / 120), gap = h / 24;
  ctx.fillStyle = '#0B3C1F'; ctx.fillRect(0, 0, w, h);
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  for (let i = 0, n = Math.ceil((h * 1.1) / gap); i < n; i++) {
    const y0 = h * 0.2 + i * gap, fade = Math.max(0, 1 - i / 8);
    ctx.beginPath();
    for (let x = -step; x <= w + step; x += step) {
      const [px, py] = warp(x, y0, w, h, t);
      const hy = py + (horizon(x, h, t) - h * 0.27) * fade;
      x === -step ? ctx.moveTo(px, hy) : ctx.lineTo(px, hy);
    }
    ctx.strokeStyle = `hsl(${138 + (i % 3) * 4} 58% ${15 + 7 * Math.sin(i * 0.8 + t * 0.2)}%)`;
    ctx.lineWidth = gap * 1.2;
    ctx.stroke();
    if (i % 4 === 1) {                                   // cream highlights: light catching a mown stripe
      ctx.strokeStyle = `rgba(244,239,216,${0.42 + 0.3 * Math.sin(i * 1.7)})`;
      ctx.lineWidth = gap * (0.14 + 0.1 * Math.abs(Math.sin(i)));
      ctx.translate(0, -gap * 0.3); ctx.stroke(); ctx.translate(0, gap * 0.3);
    }
  }
  ctx.fillStyle = SKY;                                   // sky on top, so stripes never cross the horizon
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(w, 0);
  for (let x = w; x >= 0; x -= step) ctx.lineTo(x, horizon(x, h, t));
  ctx.closePath(); ctx.fill();
  ctx.beginPath();
  for (let x = 0; x <= w; x += step) (x === 0 ? ctx.moveTo(x, horizon(x, h, t)) : ctx.lineTo(x, horizon(x, h, t)));
  ctx.strokeStyle = CREAM; ctx.lineWidth = Math.max(4, h * 0.016); ctx.globalAlpha = 0.9; ctx.stroke(); ctx.globalAlpha = 1;
}

let backdrop = null;

/** Create (once) the fixed backdrop layers and return a controller: { setAnimated(bool) }. */
export function mountBackdrop() {
  if (backdrop) return backdrop;
  const mk = (tag, id, attrs = {}) => { const e = document.createElement(tag); e.id = id; e.setAttribute('aria-hidden', 'true'); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); document.body.prepend(e); return e; };
  const dim = mk('div', 'dim'), grain = mk('div', 'grain'), canvas = mk('canvas', 'backdrop');   // prepended: canvas ends up first, behind the others
  const ctx = canvas.getContext('2d');
  let t = 3.2, last = performance.now(), raf = 0, animated = false, visible = !document.hidden;
  const draw = () => paintFlow(ctx, canvas.width, canvas.height, t);
  const fit = () => { canvas.width = Math.max(360, Math.round(canvas.clientWidth * 0.55)); canvas.height = Math.max(240, Math.round(canvas.clientHeight * 0.55)); draw(); };
  const frame = now => {
    if (!animated || !canvas.isConnected) { raf = 0; return; }
    raf = requestAnimationFrame(frame);
    if (!visible || now - last < 40) return;             // about 25 fps is plenty for slow liquid motion
    t += ((now - last) / 1000) * 0.55; last = now; draw();
  };
  new ResizeObserver(fit).observe(canvas);
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; last = performance.now(); });
  fit();                                                 // always one painted frame: this is also the still image for reduced motion
  backdrop = {
    dim, grain, canvas,
    setAnimated(on) {
      animated = !!on && !prefersReduced();
      document.body.classList.toggle('bg-animated', animated);
      if (animated && !raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
      if (!animated) { cancelAnimationFrame(raf); raf = 0; }
    },
  };
  return backdrop;
}

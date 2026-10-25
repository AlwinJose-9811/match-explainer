// Landing page: a flowing "liquid pitch" (canvas, drawn in code), a real goal's ball path as a multi-exposure trail
// (SVG, from the match data), and the entry points. Everything is drawn here: no images, fonts or requests are loaded.
// With reduced motion the background is a single still frame and the trail is shown complete.
import { h, s } from './dom.js';

const SKY = '#1D4E9E', CREAM = '#F4EFD8';
const prefersReduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- pure helpers (also tested under Node) ----------
/** Smooth SVG path through points (Catmull-Rom converted to cubic Beziers). */
export function catmullRom(pts) {
  if (pts.length < 2) return '';
  const f = n => n.toFixed(2);
  let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    d += ` C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d;
}

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

function startFlow(canvas) {
  const ctx = canvas.getContext('2d');
  let t = 3.2, last = performance.now(), raf = 0, visible = !document.hidden;
  const draw = () => paintFlow(ctx, canvas.width, canvas.height, t);
  const fit = () => { canvas.width = Math.max(360, Math.round(canvas.clientWidth * 0.55)); canvas.height = Math.max(240, Math.round(canvas.clientHeight * 0.55)); draw(); };
  const frame = now => {
    if (!canvas.isConnected) return;                     // the page was left
    raf = requestAnimationFrame(frame);
    if (!visible || now - last < 40) return;             // about 25 fps is plenty for slow liquid motion
    t += ((now - last) / 1000) * 0.55; last = now; draw();
  };
  new ResizeObserver(fit).observe(canvas);
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; last = performance.now(); });
  fit();                                                 // always paint one frame (this is the still image for reduced motion)
  if (!prefersReduced()) raf = requestAnimationFrame(frame);
  return () => cancelAnimationFrame(raf);
}

// ---------- the ball-path trail ----------
const pitchLines = () => {
  const m = a => s('path', { d: a, fill: 'none', stroke: CREAM, 'stroke-opacity': .24, 'stroke-width': .35 });
  return s('g', null, m('M0 0H120V80H0Z'), m('M60 0V80'), m('M60 30a10 10 0 1 0 .01 0Z'), m('M0 18H18V62H0'), m('M120 18H102V62H120'), m('M0 30H6V50H0'), m('M120 30H114V50H120'));
};

function ball(x, y, r, delay) {
  const pent = [0, 1, 2, 3, 4].map(i => `${(r * 0.42 * Math.sin(i * 1.2566)).toFixed(2)},${(-r * 0.42 * Math.cos(i * 1.2566)).toFixed(2)}`).join(' ');
  return s('g', { class: 'ball', transform: `translate(${x.toFixed(2)} ${y.toFixed(2)})`, style: `--d:${delay}s` },
    s('ellipse', { cx: -r * 0.9, cy: r * 0.95, rx: r * 1.15, ry: r * 0.45, fill: '#000', opacity: .32 }),
    s('circle', { r, fill: '#F7F4E8', stroke: '#16301F', 'stroke-width': r * 0.08 }),
    s('polygon', { points: pent, fill: '#16301F' }),
    ...[0, 1, 2, 3, 4].map(i => s('line', { x1: (r * 0.42 * Math.sin(i * 1.2566)).toFixed(2), y1: (-r * 0.42 * Math.cos(i * 1.2566)).toFixed(2),
      x2: (r * 0.95 * Math.sin(i * 1.2566)).toFixed(2), y2: (-r * 0.95 * Math.cos(i * 1.2566)).toFixed(2), stroke: '#16301F', 'stroke-width': r * 0.07 })));
}

function runner(x, y, k, shirt, shorts, flip = 1) {
  const L = (x1, y1, x2, y2, w, c) => s('line', { x1, y1, x2, y2, stroke: c, 'stroke-width': w, 'stroke-linecap': 'round' });
  return s('g', { class: 'runner', transform: `translate(${x} ${y}) scale(${k * flip} ${k})` },
    s('ellipse', { cx: -4, cy: 9.5, rx: 6.5, ry: 1.3, fill: '#000', opacity: .3 }),
    L(0, 3.2, -2.4, 8.4, 1.2, '#E7C9A8'), L(0, 3.2, 3.2, 7.4, 1.2, '#E7C9A8'),          // legs
    s('path', { d: 'M-1.7 -1.4 h3.4 l.6 4.8 h-4.6 z', fill: shorts }),
    s('path', { d: 'M-2.1 -5.6 h4.2 l.5 4.6 h-5.2 z', fill: shirt }),
    L(-1.9, -4.6, -4.2, -1.6, 1, shirt), L(1.9, -4.6, 4.1, -2.6, 1, shirt),            // arms
    s('circle', { cx: 0, cy: -7.4, r: 1.7, fill: '#E7C9A8' }), s('path', { d: 'M-1.7 -7.6a1.7 1.7 0 0 1 3.4 0z', fill: '#2A1B12' }));
}

function buildTrail(steps, caption) {
  const pts = [steps[0].from, ...steps.map(x => x.to)];
  const d = catmullRom(pts);
  const net = s('g', { class: 'goalnet' }, s('rect', { x: 119.2, y: 35.6, width: 4.6, height: 8.8, fill: 'rgba(244,239,216,.1)', stroke: CREAM, 'stroke-width': .35 }),
    ...Array.from({ length: 5 }, (_, i) => s('line', { x1: 119.2, y1: 37.4 + i * 1.7, x2: 123.8, y2: 37.4 + i * 1.7, stroke: CREAM, 'stroke-opacity': .45, 'stroke-width': .15 })));
  const svg = s('svg', { class: 'trail', viewBox: '-6 -8 134 98', role: 'img', 'aria-label': caption, preserveAspectRatio: 'xMidYMid meet' },
    pitchLines(), net,
    s('path', { d, class: 'glow', fill: 'none', stroke: CREAM, 'stroke-opacity': .28, 'stroke-width': 2.6, 'stroke-linecap': 'round' }),
    s('path', { d, class: 'line', fill: 'none', stroke: '#fff', 'stroke-width': .55, 'stroke-linecap': 'round' }),
    runner(13, 66, 1.0, '#F4F1E6', '#D9462B'), runner(22, 60, 0.9, '#F4F1E6', '#D9462B'), runner(50, 34, 0.95, '#2D6FD1', '#1B3E86', -1), runner(92, 55, 1.0, '#F4F1E6', '#D9462B'));
  return { svg, d };
}

/** Place a multi-exposure of balls along the finished path (needs the SVG attached to measure it). */
function placeBalls(svg, d) {
  const probe = svg.querySelector('path.line'), len = probe.getTotalLength(), n = 9, reduced = prefersReduced();
  probe.style.setProperty('--len', len.toFixed(1));
  svg.querySelector('path.glow').style.setProperty('--len', len.toFixed(1));
  for (let i = 0; i < n; i++) {                                   // bold balls that grow towards the goal, like a multi-exposure photo
    const p = probe.getPointAtLength((len * i) / (n - 1)), r = 1.7 + (i / (n - 1)) * 2.0;
    svg.append(ball(p.x, p.y, r, reduced ? 0 : 0.35 + i * 0.28));
  }
}

// ---------- the page ----------
export async function render({ index, load }) {
  let trail = null, caption = 'The path of the ball in a goal';
  try {
    const dm = await load(`${index.default}/moments.json`);
    const m = dm.moments.filter(x => x.is_goal && !x.is_penalty && x.sequence.length >= 5).sort((a, b) => b.sequence.length - a.sequence.length)[0];
    if (m) {
      const label = index.matches.find(x => x.match_id === index.default);
      const who = (dm.names && dm.names[m.player]) || m.player;
      caption = `${label.home} v ${label.away} · ${m.clock} · ${who} scores after a ${m.facts.sequence_len}-pass move`;
      trail = buildTrail(m.sequence, caption);
    }
  } catch (e) { /* the page still works without the trail */ }

  const chip = m => h('a', { class: 'lp-chip', href: `#summary?m=${m.match_id}` }, h('span', null, `${m.home} ${m.score} ${m.away}`));
  const still = prefersReduced() || /still/.test(location.hash);   // "#home?still" shows the finished composition (for screenshots)
  const node = h('section', { class: still ? 'lp lp-still' : 'lp', 'aria-labelledby': 'lp-title' },
    h('canvas', { class: 'lp-canvas', 'aria-hidden': 'true' }),
    h('div', { class: 'lp-grain', 'aria-hidden': 'true' }), h('div', { class: 'lp-scrim', 'aria-hidden': 'true' }),
    h('div', { class: 'lp-trailwrap' }, trail ? trail.svg : null,
      trail ? h('p', { class: 'lp-caption' }, caption) : null),
    h('div', { class: 'lp-copy' },
      h('p', { class: 'lp-eyebrow' }, `FIFA World Cup 2022 · ${index.matches.length} matches · plain English`),
      h('h1', { id: 'lp-title', tabindex: '-1' }, 'See why the goal ', h('em', null, 'happened.')),
      h('p', { class: 'lp-sub' }, 'Every pass, every run, both teams. Replayed in real time and explained like a friend who knows football.'),
      h('div', { class: 'lp-cta' },
        h('a', { class: 'lp-btn', href: `#summary?m=${index.default}` }, 'Explore the final ', h('span', { 'aria-hidden': 'true' }, '→')),
        h('a', { class: 'lp-link', href: `#moments?m=${index.default}` }, 'Watch the replays')),
      h('ul', { class: 'lp-feats' }, ['Replays with every player on camera', 'A commentator’s voice', 'An honest expected-goals model'].map(t => h('li', null, t)))),
    h('nav', { class: 'lp-matches', 'aria-label': 'Choose a match' }, h('span', { class: 'lp-label' }, 'Or pick a match'), index.matches.map(chip)),
    h('p', { class: 'lp-credit' }, 'Data provided by ', h('a', { href: 'https://github.com/statsbomb/open-data', target: '_blank', rel: 'noopener' }, 'StatsBomb'),
      ' · All explanations are automated analysis built from event data. The artwork on this page is drawn in code.'));

  setTimeout(() => {                                       // after the router has attached the page
    const cv = node.querySelector('canvas');
    if (cv && cv.isConnected) startFlow(cv);
    if (trail && trail.svg.isConnected) placeBalls(trail.svg, trail.d);
  }, 0);
  return node;
}

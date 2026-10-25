// Replay engine: animates a build-up sequence on the pitch (ball, arrows), with play/pause/restart,
// 0.5x / 1x speed, a scrubber, 360 snapshots with the last-defender line, and a step-by-step view
// for people who prefer reduced motion. The attacking team always attacks to the right here.
import { h, s, clear, num } from './dom.js';
import { pitchSvg, marker } from './pitch.js';
import { term } from './glossary.js';

const COMPRESSION = 0.35, MIN_STEP_S = 0.6, MAX_STEP_S = 2.0, SHOT_S = 0.9;
const NAVY = '#1F3864';
const prefersReduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Adds display start/end seconds to each step: real duration x compression, kept between 0.6 s and 2 s. */
export function timeline(steps) {
  let t = 0;
  return steps.map((st, i) => {
    const real = i < steps.length - 1 ? steps[i + 1].t - st.t : 1;
    const dur = st.kind === 'shot' ? SHOT_S : clamp(real * COMPRESSION, MIN_STEP_S, MAX_STEP_S);
    const out = { ...st, start: t, end: t + dur };
    t += dur;
    return out;
  });
}

export const stepText = (st, nm, i) => {
  const who = nm(st.player);
  const text = st.kind === 'pass' ? `${who} passes to ${nm(st.recipient) || 'a teammate'}`
    : st.kind === 'carry' ? `${who} runs with the ball`
      : `${who} shoots${st.outcome ? ` (${st.outcome === 'Goal' ? 'goal!' : st.outcome.toLowerCase()})` : ''}`;
  return `${i + 1}. ${text}${st.key ? ' — the key pass' : ''}`;
};

function defs() {
  const head = (id, color) => s('marker', { id, viewBox: '0 0 6 6', refX: 5, refY: 3, markerWidth: 4, markerHeight: 4, orient: 'auto-start-reverse' },
    s('path', { d: 'M0 0 L6 3 L0 6 z', fill: color }));
  return s('defs', null, head('ah-home', 'var(--home)'), head('ah-away', 'var(--away)'), head('ah-navy', NAVY));
}

/** Draw the sequence at `time` seconds into `layer`. Returns the index of the active step. */
function drawSequence(layer, tl, time, color, head, total) {
  let active = 0, ball = tl[0].from;
  tl.forEach((st, i) => {
    if (time < st.start) return;
    active = i;
    const frac = clamp((time - st.start) / (st.end - st.start), 0, 1), p = lerp(st.from, st.to, frac);
    ball = p;
    const done = frac >= 0.99, shot = st.kind === 'shot';
    const attrs = { x1: st.from[0], y1: st.from[1], x2: p[0], y2: p[1], stroke: shot ? NAVY : color,
      'stroke-width': shot ? 1.1 : st.key ? 0.95 : 0.6, 'stroke-linecap': 'round',
      'stroke-dasharray': st.kind === 'carry' ? '1.4 1.1' : null, 'marker-end': done ? `url(#${shot ? 'ah-navy' : head})` : null };
    layer.append(s('line', attrs));
    if (st.key) layer.append(s('text', { x: (st.from[0] + st.to[0]) / 2, y: (st.from[1] + st.to[1]) / 2 - 1.6, 'text-anchor': 'middle', fill: NAVY,
      stroke: '#fff', 'stroke-width': .9, 'paint-order': 'stroke', 'font-size': 2.3, 'font-weight': 700 }, 'KEY PASS'));
    if (!shot) layer.append(s('circle', { cx: st.from[0], cy: st.from[1], r: 1.35, fill: '#fff', stroke: color, 'stroke-width': .35 }),
      s('text', { x: st.from[0], y: st.from[1] + .55, 'text-anchor': 'middle', 'font-size': 1.6, 'font-weight': 700, fill: NAVY }, i + 1));
    else layer.append(s('circle', { cx: st.from[0], cy: st.from[1], r: 2.4, fill: 'none', stroke: NAVY, 'stroke-width': .45 }));
    if (shot && done && st.outcome === 'Goal')
      layer.append(s('text', { x: 112, y: 33, 'text-anchor': 'middle', fill: '#1E7B45', stroke: '#fff', 'stroke-width': 1, 'paint-order': 'stroke', 'font-size': 4, 'font-weight': 800 }, 'GOAL!'));
  });
  if (time >= total && tl.length) ball = tl[tl.length - 1].to;
  layer.append(s('circle', { cx: ball[0], cy: ball[1], r: 1.25, fill: '#fff', stroke: NAVY, 'stroke-width': .5 }));
  return active;
}

function drawSnapshot(layer, snap, attackSide, defendSide, gapNote) {
  if (!snap) return;
  const line = snap.offside_line_x;
  if (line != null) {
    layer.append(s('rect', { x: line, y: 0, width: 120 - line, height: 80, fill: NAVY, opacity: .07 }),
      s('line', { x1: line, y1: 0, x2: line, y2: 80, stroke: NAVY, 'stroke-width': .5, 'stroke-dasharray': '1.2 1' }),
      s('text', { x: line - .8, y: 77.5, 'text-anchor': 'end', 'font-size': 2.2, 'font-weight': 700, fill: NAVY, stroke: '#fff', 'stroke-width': .9, 'paint-order': 'stroke' },
        `Last visible defender ${num(line)}`));
    if (gapNote) layer.append(s('text', { x: line - .8, y: 74.6, 'text-anchor': 'end', 'font-size': 2.1, fill: NAVY, stroke: '#fff', 'stroke-width': .9, 'paint-order': 'stroke' }, gapNote));
  }
  for (const p of snap.players) {
    const att = p.role === 'attacker' || p.role === 'own_keeper';
    const g = s('g', { opacity: .95 }, marker(att ? attackSide : defendSide, p.x, p.y, p.actor ? 2.2 : 1.8, p.role.includes('keeper') ? 'GK' : null));
    if (p.actor) g.prepend(s('circle', { cx: p.x, cy: p.y, r: 3.1, fill: 'none', stroke: NAVY, 'stroke-width': .5 }));
    layer.append(g);
  }
}

/** Build the replay widget for one moment. Returns { node, destroy }. */
export function createReplay(moment, { teams, names }) {
  const nm = n => (n ? names[n] || n : n);
  const attackSide = moment.team, defendSide = attackSide === 'home' ? 'away' : 'home';
  const color = attackSide === 'home' ? 'var(--home)' : 'var(--away)';
  const tl = timeline(moment.sequence), total = tl[tl.length - 1].end;
  const reduced = prefersReduced();
  const st = { time: reduced ? total : 0, playing: false, speed: 1, snap: null, raf: 0, last: 0 };

  const svg = pitchSvg(`Replay of the ${moment.clock} ${moment.type} for ${teams[attackSide].name}`);
  svg.prepend(defs());
  const seqLayer = s('g'), snapLayer = s('g');
  svg.append(seqLayer, snapLayer);
  const caption = h('p', { class: 'caption', 'aria-live': 'polite' });
  const scrub = h('input', { type: 'range', min: 0, max: 1000, value: reduced ? 1000 : 0, id: 'scrub', 'aria-label': 'Move through the replay' });
  const playBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Play replay' }, '▶ Play');
  const restartBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Restart replay' }, '↺ Restart');
  const prevBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Previous step' }, '◀ Step');
  const nextBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Next step' }, 'Step ▶');
  const speedBtns = [[0.5, '0.5x'], [1, '1x']].map(([v, l]) => h('button', { type: 'button', class: 'btn', 'aria-label': `Speed ${l}`, onclick: () => { st.speed = v; paint(); } }, l));
  const stepList = h('ol', { class: 'steps', 'aria-label': 'Steps of the move' }, tl.map((x, i) => h('li', { 'data-i': i }, stepText(x, nm, i).replace(/^\d+\.\s/, ''))));
  const snapBtns = ['key_pass', 'shot'].map(k => ({ k, ok: !!moment.snapshots[k],
    btn: h('button', { type: 'button', class: 'btn', onclick: () => toggleSnap(k) }, k === 'key_pass' ? 'Players at the key pass' : 'Players at the shot') }));

  function stepStart(kind) { const i = tl.findIndex(x => kind === 'shot' ? x.kind === 'shot' : x.key); return i < 0 ? null : tl[i].start; }
  function toggleSnap(k) {
    stop();
    st.snap = st.snap === k ? null : k;
    if (st.snap) st.time = Math.max(0, (stepStart(k) ?? total) + 0.001);
    paint();
  }
  function stop() { st.playing = false; cancelAnimationFrame(st.raf); }
  function frame(now) {
    if (!st.playing || !svg.isConnected) { st.playing = false; return; }
    st.time = Math.min(total, st.time + ((now - st.last) / 1000) * st.speed);
    st.last = now;
    if (st.time >= total) st.playing = false;
    paint();
    if (st.playing) st.raf = requestAnimationFrame(frame);
  }
  function play() {
    st.snap = null;
    if (st.time >= total) st.time = 0;
    st.playing = true; st.last = performance.now();
    st.raf = requestAnimationFrame(frame);
    paint();
  }
  let current = 0;
  // Step buttons: "next" completes the current step (or the following one if it is already complete);
  // "previous" goes back to the state after the step before the current one (or the start).
  const stepDone = k => tl[k].end - 0.002;   // just inside the end, so step k is drawn complete and still the active one
  const jump = d => {
    stop(); st.snap = null;
    if (d > 0) st.time = stepDone(st.time < tl[current].end - 0.05 ? current : Math.min(current + 1, tl.length - 1));
    else st.time = current > 0 ? stepDone(current - 1) : 0;
    paint();
  };

  playBtn.addEventListener('click', () => (st.playing ? (stop(), paint()) : play()));
  restartBtn.addEventListener('click', () => { stop(); st.snap = null; st.time = 0; play(); });
  prevBtn.addEventListener('click', () => jump(-1)); nextBtn.addEventListener('click', () => jump(1));
  scrub.addEventListener('input', () => { stop(); st.snap = null; st.time = (scrub.value / 1000) * total; paint(); });

  function paint() {
    clear(seqLayer); clear(snapLayer);
    current = drawSequence(seqLayer, tl, st.time, color, `ah-${attackSide}`, total);
    if (st.snap) {
      const snap = moment.snapshots[st.snap], gap = moment.facts.gap_to_line;
      const note = st.snap === 'key_pass' && gap != null ? (gap > 0 ? `The key pass ended ${num(gap)} units beyond that line` : `The key pass ended ${num(-gap)} units short of that line`) : null;
      drawSnapshot(snapLayer, snap, attackSide, defendSide, note);
    }
    scrub.value = String(Math.round((st.time / total) * 1000));
    const a = tl[current];
    caption.textContent = st.time <= 0 ? `Press play to watch the move. ${tl.length} steps.` : `Step ${current + 1} of ${tl.length}: ${stepText(a, nm, current).replace(/^\d+\.\s/, '')}`;
    scrub.setAttribute('aria-valuetext', caption.textContent);
    stepList.querySelectorAll('li').forEach((li, i) => { li.className = i === current && st.time > 0 ? 'on' : ''; li.toggleAttribute('aria-current', i === current && st.time > 0); });
    playBtn.textContent = st.playing ? '❚❚ Pause' : '▶ Play';
    playBtn.setAttribute('aria-label', st.playing ? 'Pause replay' : 'Play replay');
    speedBtns.forEach((b, i) => b.setAttribute('aria-pressed', String([0.5, 1][i] === st.speed)));
    snapBtns.forEach(({ k, btn, ok }) => { btn.disabled = !ok; btn.setAttribute('aria-pressed', String(st.snap === k)); });
  }
  paint();

  const controls = reduced
    ? [h('p', { class: 'note' }, 'Reduced motion is on in your system, so the animation is replaced by a step-by-step view. Use the step buttons or the slider.'), prevBtn, nextBtn]
    : [playBtn, restartBtn, h('span', { class: 'ctl-sep', 'aria-hidden': 'true' }), ...speedBtns];
  const node = h('div', { class: 'replay' },
    h('div', { class: 'pitch-wrap' }, svg),
    caption,
    h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Replay controls' }, controls),
    h('div', { class: 'slider-row' }, h('label', { for: 'scrub' }, 'Scrub'), scrub),
    moment.snapshots.key_pass || moment.snapshots.shot ? h('div', null,
      h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Show the players visible on camera' }, snapBtns.map(x => x.btn)),
      h('p', { class: 'muted' }, term('visible_players', 'Visible players only'), ': the 360 data holds only the players on the TV picture. ',
        'Circles and squares are the two teams; GK marks a goalkeeper; the shaded area is behind the last visible defender.')) : null,
    h('details', { class: 'steps-box' }, h('summary', null, 'The move, step by step (text version)'), stepList),
    h('div', { class: 'legend' },
      h('span', { class: 'item' }, h('i', { class: `swatch ${attackSide}` }), `${teams[attackSide].name} attack to the right →`),
      h('span', { class: 'item' }, 'Solid line = pass · dashed line = run with the ball · dark arrow = shot')));
  return { node, destroy: () => { stop(); } };
}

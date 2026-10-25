// Replay engine. Two things move on one real-time clock:
//  1. the BALL, drawn on top as a thick line with an arrow (pass = solid, carry = dashed, shot = dark), from the event data;
//  2. the PLAYERS of both teams, reconstructed from the 360 snapshots: every player visible on the TV picture, with
//     estimated runs between snapshots. Only visible players exist in the data, so this is an estimate, not tracking.
// The attacking team always attacks to the right here. Reduced motion gives a step-by-step view instead.
import { h, s, clear, num } from './dom.js';
import { pitchSvg, marker } from './pitch.js';
import { term } from './glossary.js';

const NAVY = '#1F3864';
const TAIL_S = 0.8, FADE_IN_S = 0.4, FADE_OUT_S = 0.8, TRAIL_S = 2.0;
const prefersReduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Real-time ball timeline: each step starts at its event time and lasts the real pass/carry/shot duration. */
export function timeline(steps) {
  return steps.map((st, i) => {
    const next = steps[i + 1];
    const room = next ? Math.max(next.t - st.t, 0.2) : 2.0;
    const dur = Math.min(Math.max(st.dur ?? 0.8, 0.25), room);
    return { ...st, start: st.t, end: st.t + dur };
  });
}

export const stepText = (st, nm, i) => {
  const who = nm(st.player);
  const text = st.kind === 'pass' ? `${who} passes to ${nm(st.recipient) || 'a teammate'}`
    : st.kind === 'carry' ? `${who} runs with the ball`
      : `${who} shoots${st.outcome ? ` (${st.outcome === 'Goal' ? 'goal!' : st.outcome.toLowerCase()})` : ''}`;
  return `${i + 1}. ${text}${st.key ? ' — the key pass' : ''}`;
};

/** Position of a track at `time`, with an opacity that fades in/out where the player enters/leaves the camera view. */
export function trackAt(tr, time) {
  const p = tr.pts, first = p[0][0], last = p[p.length - 1][0];
  if (time < first - FADE_IN_S || time > last + FADE_OUT_S) return null;
  const opacity = time < first ? 1 - (first - time) / FADE_IN_S : time > last ? 1 - (time - last) / FADE_OUT_S : 1;
  if (time <= first) return { x: p[0][1], y: p[0][2], opacity };
  if (time >= last) return { x: p[p.length - 1][1], y: p[p.length - 1][2], opacity };
  let i = 1;
  while (p[i][0] < time) i++;
  const f = (time - p[i - 1][0]) / Math.max(p[i][0] - p[i - 1][0], 1e-6);
  return { x: p[i - 1][1] + (p[i][1] - p[i - 1][1]) * f, y: p[i - 1][2] + (p[i][2] - p[i - 1][2]) * f, opacity };
}

function defs() {
  const head = (id, color) => s('marker', { id, viewBox: '0 0 6 6', refX: 4.6, refY: 3, markerWidth: 3.2, markerHeight: 3.2, orient: 'auto-start-reverse' },
    s('path', { d: 'M0 0 L6 3 L0 6 z', fill: color }));
  return s('defs', null, head('ah-home', 'var(--home)'), head('ah-away', 'var(--away)'), head('ah-navy', NAVY));
}

function drawPlayers(layer, tracks, time, attackSide, defendSide, show, carrierName) {
  const seen = [];
  for (const tr of tracks) {
    const pos = trackAt(tr, time);
    if (!pos) continue;
    const side = tr.side === 'att' ? attackSide : defendSide;
    if (show.runs) {
      const pts = [];
      for (let t = Math.max(tr.pts[0][0], time - TRAIL_S); t <= Math.min(time, tr.pts[tr.pts.length - 1][0]) + 1e-9; t += 0.25) {
        const q = trackAt(tr, t);
        if (q) pts.push(`${q.x.toFixed(1)},${q.y.toFixed(1)}`);
      }
      if (pts.length > 1) layer.append(s('polyline', { points: pts.join(' '), fill: 'none', stroke: side === 'home' ? 'var(--home)' : 'var(--away)',
        'stroke-width': .45, 'stroke-linecap': 'round', opacity: .5 * pos.opacity }));
    }
    const g = s('g', { opacity: (tr.side === 'att' ? .92 : .85) * pos.opacity }, marker(side, pos.x, pos.y, 1.9, tr.keeper ? 'GK' : tr.jersey));
    if (tr.name && tr.name === carrierName) g.prepend(s('circle', { cx: pos.x, cy: pos.y, r: 3.3, fill: 'none', stroke: NAVY, 'stroke-width': .6 }));
    layer.append(g);
    if (tr.side === 'def' && !tr.keeper && pos.opacity > .5) seen.push(pos.x);
  }
  return seen;
}

function drawBall(layer, tl, time, color, head) {
  let active = 0, ball = tl[0].from;
  tl.forEach((st, i) => {
    if (time < st.start) return;
    active = i;
    const frac = clamp((time - st.start) / (st.end - st.start), 0, 1), p = lerp(st.from, st.to, frac), shot = st.kind === 'shot';
    ball = p;
    const base = { x1: st.from[0], y1: st.from[1], x2: p[0], y2: p[1], 'stroke-linecap': 'round', 'stroke-dasharray': st.kind === 'carry' ? '1.6 1.2' : null };
    const done = frac >= 0.99;
    layer.append(
      s('line', { ...base, stroke: '#fff', 'stroke-width': (shot ? 1.4 : st.key ? 1.15 : .9) + 1.0, opacity: .9 }),   // white casing keeps the ball path visible over players
      s('line', { ...base, stroke: shot ? NAVY : color, 'stroke-width': shot ? 1.4 : st.key ? 1.15 : .9, 'marker-end': done ? `url(#${shot ? 'ah-navy' : head})` : null }));
    if (st.key) layer.append(s('text', { x: (st.from[0] + st.to[0]) / 2, y: (st.from[1] + st.to[1]) / 2 - 2.2, 'text-anchor': 'middle', fill: NAVY, stroke: '#fff',
      'stroke-width': 1, 'paint-order': 'stroke', 'font-size': 2.3, 'font-weight': 700 }, 'KEY PASS'));
    if (shot && done && st.outcome === 'Goal') layer.append(s('text', { x: 108, y: 28, 'text-anchor': 'middle', fill: '#1E7B45', stroke: '#fff',
      'stroke-width': 1, 'paint-order': 'stroke', 'font-size': 4, 'font-weight': 800 }, 'GOAL!'));
  });
  tl.forEach((st, i) => {
    if (time < st.start || st.kind === 'shot') return;
    layer.append(s('circle', { cx: st.from[0], cy: st.from[1], r: 1.15, fill: '#fff', stroke: color, 'stroke-width': .3 }),
      s('text', { x: st.from[0], y: st.from[1] + .5, 'text-anchor': 'middle', 'font-size': 1.4, 'font-weight': 700, fill: NAVY }, i + 1));
  });
  layer.append(s('circle', { cx: ball[0], cy: ball[1], r: 1.55, fill: '#fff', stroke: NAVY, 'stroke-width': .6 }), s('circle', { cx: ball[0], cy: ball[1], r: .45, fill: NAVY }));
  return active;
}

function drawLine(layer, xs, gapNote) {
  if (xs.length < 2) return;
  const x = Math.max(...xs);
  layer.append(s('rect', { x, y: 0, width: 120 - x, height: 80, fill: NAVY, opacity: .07 }),
    s('line', { x1: x, y1: 0, x2: x, y2: 80, stroke: NAVY, 'stroke-width': .5, 'stroke-dasharray': '1.2 1' }),
    s('text', { x: x - .8, y: 77.5, 'text-anchor': 'end', 'font-size': 2.2, 'font-weight': 700, fill: NAVY, stroke: '#fff', 'stroke-width': .9, 'paint-order': 'stroke' }, `Last visible defender ${num(x)}`));
  if (gapNote) layer.append(s('text', { x: x - .8, y: 74.6, 'text-anchor': 'end', 'font-size': 2.1, fill: NAVY, stroke: '#fff', 'stroke-width': .9, 'paint-order': 'stroke' }, gapNote));
}

/** Build the replay widget for one moment. Returns { node, destroy }. */
export function createReplay(moment, { teams, names }) {
  const nm = n => (n ? names[n] || n : n);
  const attackSide = moment.team, defendSide = attackSide === 'home' ? 'away' : 'home';
  const color = attackSide === 'home' ? 'var(--home)' : 'var(--away)';
  const tl = timeline(moment.sequence), mv = moment.movement;
  const tStart = mv ? Math.min(0, mv.t_start) : 0;
  const tEnd = Math.max(tl[tl.length - 1].end, mv ? mv.t_end : 0) + TAIL_S;
  const reduced = prefersReduced();
  const st = { time: reduced ? tEnd : tStart, playing: false, speed: 1, line: false, raf: 0, last: 0 };
  const show = { players: !!mv, runs: true };

  const svg = pitchSvg(`Replay of the ${moment.clock} ${moment.type} for ${teams[attackSide].name}`);
  svg.prepend(defs());
  const lineLayer = s('g'), playerLayer = s('g'), ballLayer = s('g');
  svg.append(lineLayer, playerLayer, ballLayer);
  const caption = h('p', { class: 'caption', 'aria-live': 'polite' });
  const scrub = h('input', { type: 'range', min: 0, max: 1000, value: reduced ? 1000 : 0, id: 'scrub', 'aria-label': 'Move through the replay' });
  const playBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Play replay' }, '▶ Play');
  const restartBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Restart replay' }, '↺ Restart');
  const prevBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Previous step' }, '◀ Step');
  const nextBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Next step' }, 'Step ▶');
  const speedBtns = [[0.5, '0.5x'], [1, '1x'], [2, '2x']].map(([v, l]) => h('button', { type: 'button', class: 'btn', 'aria-label': `Speed ${l}`, onclick: () => { st.speed = v; paint(); } }, l));
  const toggles = [['players', 'Other players'], ['runs', 'Runs'], ['line', 'Last defender line']].map(([k, l]) => ({ k, btn: h('button', { type: 'button', class: 'btn',
    onclick: () => { if (k === 'line') st.line = !st.line; else show[k] = !show[k]; paint(); } }, l) }));
  const stepList = h('ol', { class: 'steps', 'aria-label': 'Steps of the move' }, tl.map((x, i) => h('li', { 'data-i': i }, stepText(x, nm, i).replace(/^\d+\.\s/, ''))));
  const keyIdx = tl.findIndex(x => x.key), shotIdx = tl.findIndex(x => x.kind === 'shot');
  const freezeBtns = [['key', 'Freeze at the key pass', keyIdx], ['shot', 'Freeze at the shot', shotIdx]].map(([k, l, i]) => ({ k, i, btn: h('button', { type: 'button', class: 'btn', disabled: i < 0,
    onclick: () => { stop(); st.line = true; st.time = tl[i].start + 0.001; paint(); } }, l) }));

  let current = 0;
  const stepDone = k => tl[k].end - 0.002;   // just inside the end, so step k is drawn complete and is still the active one
  function stop() { st.playing = false; cancelAnimationFrame(st.raf); }
  function frame(now) {
    if (!st.playing || !svg.isConnected) { st.playing = false; return; }
    st.time = Math.min(tEnd, st.time + ((now - st.last) / 1000) * st.speed);
    st.last = now;
    if (st.time >= tEnd) st.playing = false;
    paint();
    if (st.playing) st.raf = requestAnimationFrame(frame);
  }
  function play() {
    if (st.time >= tEnd - 0.01) st.time = tStart;
    st.playing = true; st.last = performance.now();
    st.raf = requestAnimationFrame(frame);
    paint();
  }
  const jump = d => {
    stop();
    if (d > 0) st.time = stepDone(st.time < tl[current].end - 0.05 ? current : Math.min(current + 1, tl.length - 1));
    else st.time = current > 0 ? stepDone(current - 1) : tStart;
    paint();
  };
  playBtn.addEventListener('click', () => (st.playing ? (stop(), paint()) : play()));
  restartBtn.addEventListener('click', () => { stop(); st.time = tStart; play(); });
  prevBtn.addEventListener('click', () => jump(-1)); nextBtn.addEventListener('click', () => jump(1));
  scrub.addEventListener('input', () => { stop(); st.time = tStart + (scrub.value / 1000) * (tEnd - tStart); paint(); });

  function paint() {
    clear(lineLayer); clear(playerLayer); clear(ballLayer);
    const a0 = tl.filter(x => x.start <= st.time).pop() || tl[0];
    const defenders = mv && show.players ? drawPlayers(playerLayer, mv.tracks, st.time, attackSide, defendSide, show, a0.player) : [];
    current = drawBall(ballLayer, tl, st.time, color, `ah-${attackSide}`);
    if (st.line && mv) {
      const gap = moment.facts.gap_to_line, isKey = tl[current].key;
      drawLine(lineLayer, mv.tracks.filter(t => t.side === 'def' && !t.keeper).map(t => trackAt(t, st.time)).filter(p => p && p.opacity > .5).map(p => p.x),
        isKey && gap != null ? (gap > 0 ? `The key pass ended ${num(gap)} units beyond that line` : `The key pass ended ${num(-gap)} units short of that line`) : null);
    }
    scrub.value = String(Math.round(((st.time - tStart) / (tEnd - tStart)) * 1000));
    const a = tl[current];
    caption.textContent = st.time <= tStart + 0.01 && !reduced ? `Press play to watch the move. ${tl.length} steps, in real time.` : `Step ${current + 1} of ${tl.length}: ${stepText(a, nm, current).replace(/^\d+\.\s/, '')}`;
    scrub.setAttribute('aria-valuetext', caption.textContent);
    stepList.querySelectorAll('li').forEach((li, i) => { const on = i === current && st.time > tStart + 0.01; li.className = on ? 'on' : ''; li.toggleAttribute('aria-current', on); });
    playBtn.textContent = st.playing ? '❚❚ Pause' : '▶ Play';
    playBtn.setAttribute('aria-label', st.playing ? 'Pause replay' : 'Play replay');
    speedBtns.forEach((b, i) => b.setAttribute('aria-pressed', String([0.5, 1, 2][i] === st.speed)));
    toggles.forEach(({ k, btn }) => { btn.disabled = !mv; btn.setAttribute('aria-pressed', String(k === 'line' ? st.line : show[k])); });
  }
  paint();

  const q = mv && mv.quality;
  const controls = reduced
    ? [h('p', { class: 'note' }, 'Reduced motion is on in your system, so the animation is replaced by a step-by-step view. Use the step buttons or the slider.'), prevBtn, nextBtn]
    : [playBtn, restartBtn, h('span', { class: 'ctl-sep', 'aria-hidden': 'true' }), ...speedBtns];
  const node = h('div', { class: 'replay' },
    h('div', { class: 'pitch-wrap' }, svg),
    caption,
    h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Replay controls' }, controls),
    h('div', { class: 'slider-row' }, h('label', { for: 'scrub' }, 'Scrub'), scrub),
    h('div', { class: 'btn-row', role: 'group', 'aria-label': 'What to show on the pitch' }, h('span', { class: 'muted' }, 'Show:'), toggles.map(x => x.btn), freezeBtns.map(x => x.btn)),
    h('div', { class: 'legend' },
      h('span', { class: 'item' }, h('i', { class: `swatch ${attackSide}` }), `${teams[attackSide].name} attack to the right →`),
      h('span', { class: 'item' }, h('i', { class: `swatch ${defendSide}` }), `${teams[defendSide].name} defend`),
      h('span', { class: 'item' }, 'Thick line with an arrow = the ball: solid = pass, dashed = run with the ball, dark = shot. Dots = players (numbers are shirt numbers); thin faint lines = recent runs.')),
    mv ? h('p', { class: 'muted' }, term('visible_players', 'Visible players only'),
      `: the other players come from ${q.snapshots} camera snapshots taken at each action (about ${num(q.avg_visible, 0)} visible players each, longest gap ${num(q.max_gap_s)} s). `
      + 'Their runs between snapshots are smoothed estimates, so exact routes may differ, and players off the TV picture are not shown. Numbered players are the ones named in the event data.')
      : h('p', { class: 'muted' }, 'Player positions are not available for this moment, so only the ball is shown.'),
    h('details', { class: 'steps-box' }, h('summary', null, 'The move, step by step (text version)'), stepList));
  return { node, destroy: () => { stop(); } };
}

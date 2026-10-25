// Replay engine. Two things move on one real-time clock:
//  1. the BALL, drawn on top as a thick white line with an arrow (gold for the shot), from the event data;
//  2. the PLAYERS of both teams, reconstructed from the 360 snapshots: every player visible on the TV picture, with
//     estimated runs between snapshots. Only visible players exist in the data, so this is an estimate, not tracking.
// Extras: live distance from the ball to the closest defender, a floating player card, a glass transport bar, a live
// last-defender line and a freeze at the key pass / shot. The attacking team always attacks to the right here.
import { h, s, clear, num } from './dom.js';
import { pitchSvg, marker } from './pitch.js';
import { stage } from './stage.js';
import { term } from './glossary.js';

const INK = '#F4EFD8', HALO = 'rgba(4,20,11,.9)', GOLD = '#FFD84A', WHITE = '#FFFFFF', CASING = 'rgba(4,20,11,.72)', LIME = '#C9E265';
const TAIL_S = 0.8, FADE_IN_S = 0.4, FADE_OUT_S = 0.8, TRAIL_S = 2.0;
const prefersReduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const mmss = sec => `${Math.floor(Math.max(0, sec) / 60)}:${String(Math.floor(Math.max(0, sec) % 60)).padStart(2, '0')}`;

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
  return s('defs', null, head('ah-pass', WHITE), head('ah-key', LIME), head('ah-shot', GOLD));
}

const halo = (extra = {}) => ({ stroke: HALO, 'stroke-width': 1, 'paint-order': 'stroke', 'font-weight': 800, ...extra });

/** Players of both teams at `time`. Returns the visible non-keeper defenders as [x, y] pairs. */
function drawPlayers(layer, tracks, time, attackSide, defendSide, show, carrierName) {
  const defenders = [];
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
      if (pts.length > 1) layer.append(s('polyline', { points: pts.join(' '), fill: 'none', stroke: side === 'home' ? '#8CC0F5' : '#F5A66B',
        'stroke-width': .45, 'stroke-linecap': 'round', opacity: .55 * pos.opacity }));
    }
    const g = s('g', { opacity: (tr.side === 'att' ? .96 : .9) * pos.opacity }, marker(side, pos.x, pos.y, 1.9, tr.keeper ? 'GK' : tr.jersey));
    if (tr.name && tr.name === carrierName) g.prepend(s('circle', { cx: pos.x, cy: pos.y, r: 3.4, fill: 'none', stroke: GOLD, 'stroke-width': .6 }));
    layer.append(g);
    if (tr.side === 'def' && !tr.keeper && pos.opacity > .5) defenders.push([pos.x, pos.y]);
  }
  return defenders;
}

/** The ball path (white casing, then a bold line on top) and the ball itself. Returns { active, ball }. */
function drawBall(layer, tl, time) {
  let active = 0, ball = tl[0].from;
  tl.forEach((st, i) => {
    if (time < st.start) return;
    active = i;
    const frac = clamp((time - st.start) / (st.end - st.start), 0, 1), p = lerp(st.from, st.to, frac), shot = st.kind === 'shot';
    ball = p;
    const w = shot ? 1.5 : st.key ? 1.2 : .9, done = frac >= 0.99;
    const base = { x1: st.from[0], y1: st.from[1], x2: p[0], y2: p[1], 'stroke-linecap': 'round', 'stroke-dasharray': st.kind === 'carry' ? '1.6 1.2' : null };
    layer.append(
      s('line', { ...base, stroke: CASING, 'stroke-width': w + 1.2 }),    // dark casing keeps the ball path visible over players and stripes
      s('line', { ...base, stroke: shot ? GOLD : st.key ? LIME : WHITE, 'stroke-width': w, 'marker-end': done ? `url(#${shot ? 'ah-shot' : st.key ? 'ah-key' : 'ah-pass'})` : null }));
    if (st.key) layer.append(s('text', { x: st.from[0], y: st.from[1] + 4.6, 'text-anchor': 'middle', fill: LIME, 'font-size': 2.3, ...halo() }, 'KEY PASS'));   // below the start of the pass, away from the floating card
    if (shot && done && st.outcome === 'Goal') layer.append(s('text', { x: 108, y: 28, 'text-anchor': 'middle', fill: LIME, 'font-size': 4.2, ...halo({ 'stroke-width': 1.2, 'font-weight': 900 }) }, 'GOAL!'));
  });
  tl.forEach((st, i) => {
    if (time < st.start || st.kind === 'shot') return;
    layer.append(s('circle', { cx: st.from[0], cy: st.from[1], r: 1.2, fill: '#0B2A18', stroke: WHITE, 'stroke-width': .3 }),
      s('text', { x: st.from[0], y: st.from[1] + .5, 'text-anchor': 'middle', 'font-size': 1.4, 'font-weight': 800, fill: WHITE }, i + 1));
  });
  const pent = [0, 1, 2, 3, 4].map(i => `${(ball[0] + 0.7 * Math.sin(i * 1.2566)).toFixed(2)},${(ball[1] - 0.7 * Math.cos(i * 1.2566)).toFixed(2)}`).join(' ');
  layer.append(s('ellipse', { cx: ball[0] - 1, cy: ball[1] + 1.4, rx: 1.9, ry: .7, fill: '#000', opacity: .4 }),
    s('circle', { cx: ball[0], cy: ball[1], r: 1.7, fill: '#F7F4E8', stroke: '#16301F', 'stroke-width': .18 }), s('polygon', { points: pent, fill: '#16301F' }));
  return { active, ball };
}

function drawLine(layer, xs, gapNote) {
  if (xs.length < 2) return;
  const x = Math.max(...xs);
  layer.append(s('rect', { x, y: 0, width: 120 - x, height: 80, fill: '#000', opacity: .16 }),
    s('line', { x1: x, y1: 0, x2: x, y2: 80, stroke: LIME, 'stroke-width': .5, 'stroke-dasharray': '1.2 1' }),
    s('text', { x: x - .8, y: 77.5, 'text-anchor': 'end', 'font-size': 2.2, fill: LIME, ...halo({ 'font-weight': 700 }) }, `Last visible defender ${num(x)}`));
  if (gapNote) layer.append(s('text', { x: x - .8, y: 74.6, 'text-anchor': 'end', 'font-size': 2.1, fill: INK, ...halo({ 'font-weight': 600 }) }, gapNote));
}

/** Dashed line from the ball to the closest visible defender, with its length in yards (1 pitch unit is about 1 yard). */
function drawClosest(layer, ball, defenders) {
  if (!defenders.length) return null;
  const near = defenders.reduce((a, b) => (dist(ball, a) <= dist(ball, b) ? a : b)), d = dist(ball, near);
  layer.append(s('line', { x1: ball[0], y1: ball[1], x2: near[0], y2: near[1], stroke: INK, 'stroke-width': .4, 'stroke-dasharray': '1.1 .9', opacity: .9 }),
    s('text', { x: (ball[0] + near[0]) / 2, y: (ball[1] + near[1]) / 2 - 1, 'text-anchor': 'middle', 'font-size': 2.1, fill: INK, ...halo({ 'font-weight': 700 }) }, `${num(d)} yd`));
  return d;
}

const speedSeg = (st, paint) => [[0.5, '0.5x'], [1, '1x'], [2, '2x']].map(([v, l]) =>
  h('button', { type: 'button', class: 'seg-btn', 'aria-label': `Speed ${l}`, onclick: () => { st.speed = v; paint(); } }, l));

/** Build the replay widget for one moment. Returns { node, destroy }. */
export function createReplay(moment, { teams, names }) {
  const nm = n => (n ? names[n] || n : n);
  const attackSide = moment.team, defendSide = attackSide === 'home' ? 'away' : 'home';
  const tl = timeline(moment.sequence), mv = moment.movement;
  const tStart = mv ? Math.min(0, mv.t_start) : 0;
  const tEnd = Math.max(tl[tl.length - 1].end, mv ? mv.t_end : 0) + TAIL_S;
  const reduced = prefersReduced();
  const st = { time: reduced ? tEnd : tStart, playing: false, speed: 1, line: false, raf: 0, last: 0 };
  const at = Number(new URLSearchParams(location.hash.split('?')[1] || '').get('at'));   // "&at=0.8" opens the replay 80% of the way through
  if (location.hash.includes('at=') && at >= 0 && at <= 1) st.time = tStart + at * (tEnd - tStart);
  const show = { players: !!mv, runs: true, dist: !!mv };

  const svg = pitchSvg(`Replay of the ${moment.clock} ${moment.type} for ${teams[attackSide].name}`);
  svg.append(defs());
  const lineLayer = s('g'), playerLayer = s('g'), distLayer = s('g'), ballLayer = s('g');
  svg.append(lineLayer, playerLayer, distLayer, ballLayer);
  const stg = stage(svg);
  const caption = h('p', { class: 'caption pill', 'aria-live': 'polite' });
  stg.hud.prepend(caption);
  const callout = h('div', { class: 'callout', hidden: true, 'aria-hidden': 'true' });
  stg.overlay.append(callout);

  const scrub = h('input', { type: 'range', min: 0, max: 1000, value: reduced ? 1000 : 0, id: 'scrub', 'aria-label': 'Move through the replay' });
  const playBtn = h('button', { type: 'button', class: 'round', 'aria-label': 'Play replay' }, '▶');
  const restartBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Restart replay' }, '↺ Restart');
  const prevBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Previous step' }, '◀ Step');
  const nextBtn = h('button', { type: 'button', class: 'btn', 'aria-label': 'Next step' }, 'Step ▶');
  const nowT = h('span', { class: 'time' }), totT = h('span', { class: 'time' }, mmss(tEnd - tStart));
  const speedBtns = speedSeg(st, () => paint());
  const sw = (k, label, get, set) => ({ k, get, btn: h('button', { type: 'button', class: 'switch', onclick: () => { set(); paint(); } }, h('i', { 'aria-hidden': 'true' }), label) });
  const switches = [sw('players', 'Other players', () => show.players, () => { show.players = !show.players; }),
    sw('runs', 'Runs', () => show.runs, () => { show.runs = !show.runs; }),
    sw('dist', 'Distances', () => show.dist, () => { show.dist = !show.dist; }),
    sw('line', 'Last defender line', () => st.line, () => { st.line = !st.line; })];
  const stepList = h('ol', { class: 'steps', 'aria-label': 'Steps of the move' }, tl.map((x, i) => h('li', null, h('b', { class: 'n', 'aria-hidden': 'true' }, i + 1), h('span', null, stepText(x, nm, i).replace(/^\d+\.\s/, '')))));
  const keyIdx = tl.findIndex(x => x.key), shotIdx = tl.findIndex(x => x.kind === 'shot');
  const freezeBtns = [['key', 'Freeze at the key pass', keyIdx], ['shot', 'Freeze at the shot', shotIdx]].map(([k, l, i]) => ({ k, i, btn: h('button', { type: 'button', class: 'btn', disabled: i < 0,
    onclick: () => { stop(); st.line = true; st.time = tl[i].start + 0.001; paint(); } }, l) }));

  let current = 0, nearest = null;
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

  /** Floating player card next to the ball (like a broadcast overlay): who, what, how far, and for a shot the chance quality. */
  function paintCallout(step, ball, d, idx) {
    if (st.time <= tStart + 0.01 && !reduced) { callout.hidden = true; return; }
    const len = dist(step.from, step.to), rows = [];
    rows.push(step.kind === 'pass' ? ['Pass to', nm(step.recipient) || 'a teammate'] : step.kind === 'carry' ? ['Action', 'Run with the ball'] : ['Shot', step.outcome === 'Goal' ? 'Goal!' : (step.outcome || '')]);
    if (step.kind !== 'shot') rows.push(['Length', `${num(len)} yd`]);
    if (step.kind === 'shot' && moment.xg_model != null) rows.push(['Chance quality', `${num(moment.xg_model, 2)} xG`]);
    if (d != null) rows.push(['Closest defender', `${num(d)} yd`]);
    if (step.key) rows.push(['', 'The key pass']);
    clear(callout).append(h('header', null, h('span', { class: `tok ${attackSide}` }, idx + 1), h('strong', null, nm(step.player))),
      h('dl', null, rows.map(([k, v]) => [h('dt', null, k), h('dd', null, v)])));
    callout.style.left = `${(ball[0] / 120) * 100}%`; callout.style.top = `${(ball[1] / 80) * 100}%`;
    callout.classList.toggle('flip', ball[0] > 78); callout.classList.toggle('below', ball[1] < 22);
    callout.hidden = false;
  }

  function paint() {
    clear(lineLayer); clear(playerLayer); clear(distLayer); clear(ballLayer);
    const a0 = tl.filter(x => x.start <= st.time).pop() || tl[0];
    const defenders = mv && show.players ? drawPlayers(playerLayer, mv.tracks, st.time, attackSide, defendSide, show, a0.player) : [];
    const b = drawBall(ballLayer, tl, st.time);
    current = b.active;
    nearest = show.dist && st.time > tStart + 0.01 ? drawClosest(distLayer, b.ball, defenders) : null;
    if (st.line && mv) {
      const gap = moment.facts.gap_to_line, isKey = tl[current].key;
      drawLine(lineLayer, mv.tracks.filter(t => t.side === 'def' && !t.keeper).map(t => trackAt(t, st.time)).filter(p => p && p.opacity > .5).map(p => p.x),
        isKey && gap != null ? (gap > 0 ? `The key pass ended ${num(gap)} units beyond that line` : `The key pass ended ${num(-gap)} units short of that line`) : null);
    }
    scrub.value = String(Math.round(((st.time - tStart) / (tEnd - tStart)) * 1000));
    scrub.style.setProperty('--fill', `${scrub.value / 10}%`);
    nowT.textContent = mmss(st.time - tStart);
    const a = tl[current];
    caption.textContent = st.time <= tStart + 0.01 && !reduced ? `Press play to watch the move · ${tl.length} steps, in real time` : `Step ${current + 1} of ${tl.length}: ${stepText(a, nm, current).replace(/^\d+\.\s/, '')}`;
    scrub.setAttribute('aria-valuetext', caption.textContent);
    paintCallout(a, b.ball, nearest, current);
    stepList.querySelectorAll('li').forEach((li, i) => { const on = i === current && st.time > tStart + 0.01; li.className = on ? 'on' : ''; li.toggleAttribute('aria-current', on); });
    playBtn.textContent = st.playing ? '❚❚' : '▶';
    playBtn.setAttribute('aria-label', st.playing ? 'Pause replay' : 'Play replay');
    speedBtns.forEach((b2, i) => b2.setAttribute('aria-pressed', String([0.5, 1, 2][i] === st.speed)));
    switches.forEach(({ get, btn }) => { btn.disabled = !mv; btn.setAttribute('aria-pressed', String(!!get() && !!mv)); });
  }
  paint();

  const q = mv && mv.quality, token = (side, t) => h('span', { class: `tok ${side}`, 'aria-hidden': 'true' }, t == null ? '' : String(t));
  const jerseyOf = {};
  (mv ? mv.tracks : []).forEach(t => { if (t.name && t.jersey != null) jerseyOf[t.name] = t.jersey; });
  const inMove = [...new Set(moment.sequence.flatMap(x => [x.player, x.recipient]).filter(Boolean))];
  const transport = reduced
    ? h('div', { class: 'transport' }, h('p', { class: 'note' }, 'Reduced motion is on in your system, so the animation is replaced by a step-by-step view. Use the step buttons or the slider.'), prevBtn, nextBtn,
      h('label', { for: 'scrub', class: 'visually-hidden' }, 'Scrub'), scrub)
    : h('div', { class: 'transport', role: 'group', 'aria-label': 'Replay controls' }, playBtn, restartBtn, nowT,
      h('label', { for: 'scrub', class: 'visually-hidden' }, 'Scrub'), scrub, totT, h('div', { class: 'seg', role: 'group', 'aria-label': 'Replay speed' }, speedBtns));
  const node = h('div', { class: 'replay' },
    stg.node, transport,
    h('div', { class: 'btn-row switches', role: 'group', 'aria-label': 'What to show on the pitch' }, switches.map(x => x.btn), freezeBtns.map(x => x.btn)),
    h('div', { class: 'legend' },
      h('span', { class: 'item' }, h('i', { class: `swatch ${attackSide}` }), `${teams[attackSide].name} attack to the right →`),
      h('span', { class: 'item' }, h('i', { class: `swatch ${defendSide}` }), `${teams[defendSide].name} defend`),
      h('span', { class: 'item' }, 'White line with an arrow = the ball (dashed = a run with the ball, lime = the key pass, gold = the shot). Tokens = players; faint lines = recent runs; the dashed line to a defender shows the gap in yards.')),
    mv ? h('p', { class: 'muted' }, term('visible_players', 'Visible players only'),
      `: the other players come from ${q.snapshots} camera snapshots taken at each action (about ${num(q.avg_visible, 0)} visible players each, longest gap ${num(q.max_gap_s)} s). `
      + 'Their runs between snapshots are smoothed estimates, so exact routes may differ, and players off the TV picture are not shown. Numbered players are the ones named in the event data.')
      : h('p', { class: 'muted' }, 'Player positions are not available for this moment, so only the ball is shown.'),
    h('div', { class: 'grid2 panels' },
      h('section', { class: 'card panel', 'aria-label': 'The move, step by step' }, h('h2', null, 'The move'), stepList),
      h('section', { class: 'card panel', 'aria-label': 'Players in the move' }, h('h2', null, 'Players in the move'),
        h('ul', { class: 'squad' }, inMove.map(n => h('li', null, token(attackSide, jerseyOf[n]), h('span', null, nm(n))))),
        h('p', { class: 'muted small' }, `${teams[attackSide].name}'s players involved before the shot. Shirt numbers appear when the data names the player.`))));
  return { node, destroy: () => { stop(); } };
}

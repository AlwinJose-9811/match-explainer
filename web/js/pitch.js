// SVG pitch factory (120 x 80 viewBox, StatsBomb units) and the Pitch page: average positions, lines, shape.
import { h, s, clear, num, pct } from './dom.js';
import { term } from './glossary.js';

/** Pitch SVG with standard markings. Home attacks right; everything is drawn in the 0..120 x 0..80 frame. */
export function pitchSvg(label) {
  const m = (tag, a) => s(tag, { class: 'mark', ...a });
  return s('svg', { class: 'pitch', viewBox: '0 0 120 80', role: 'img', 'aria-label': label, preserveAspectRatio: 'xMidYMid meet' },
    s('rect', { x: 0, y: 0, width: 120, height: 80, fill: 'var(--pitch)' }),
    m('rect', { x: 0, y: 0, width: 120, height: 80 }), m('line', { x1: 60, y1: 0, x2: 60, y2: 80 }),
    m('circle', { cx: 60, cy: 40, r: 10 }), s('circle', { cx: 60, cy: 40, r: .6, fill: 'var(--pitch-line)' }),
    m('rect', { x: 0, y: 18, width: 18, height: 44 }), m('rect', { x: 102, y: 18, width: 18, height: 44 }),
    m('rect', { x: 0, y: 30, width: 6, height: 20 }), m('rect', { x: 114, y: 30, width: 6, height: 20 }),
    s('circle', { cx: 12, cy: 40, r: .6, fill: 'var(--pitch-line)' }), s('circle', { cx: 108, cy: 40, r: .6, fill: 'var(--pitch-line)' }),
    m('path', { d: 'M18 32 A10 10 0 0 1 18 48' }), m('path', { d: 'M102 32 A10 10 0 0 0 102 48' }),
    s('rect', { x: -1.6, y: 36, width: 1.6, height: 8, fill: '#fff', stroke: 'var(--pitch-line)', 'stroke-width': .3 }),
    s('rect', { x: 120, y: 36, width: 1.6, height: 8, fill: '#fff', stroke: 'var(--pitch-line)', 'stroke-width': .3 }));
}

/** A team marker: circle for home, square for away, with an optional number inside. */
export function marker(side, x, y, r, text) {
  const color = side === 'home' ? 'var(--home)' : 'var(--away)';
  const shape = side === 'home'
    ? s('circle', { cx: x, cy: y, r, fill: color, stroke: '#fff', 'stroke-width': .5 })
    : s('rect', { x: x - r, y: y - r, width: 2 * r, height: 2 * r, rx: .5, fill: color, stroke: '#fff', 'stroke-width': .5 });
  return [shape, text != null ? s('text', { x, y: y + r * .38, 'text-anchor': 'middle', fill: '#fff', 'font-size': r * 1.05, 'font-weight': 700, 'pointer-events': 'none' }, text) : null];
}

const ROLE = { GK: 'goalkeeper', DEF: 'defender', MID: 'midfielder', ATT: 'forward' };
const LINE_LABEL = { def: 'Back', mid: 'Mid', att: 'Front' };
let ui = { win: 'full', team: 'both' };

function shapeCard(side, team, d) {
  const sh = d.shape;
  return h('div', { class: 'card' },
    h('h3', null, h('span', { class: `chip ${side}` }, team.name)),
    !sh ? h('p', { class: 'muted' }, 'Not enough touches in this window to place the lines.') : [
      h('p', null, term('block', 'Block'), ': ', h('strong', null, sh.label)),
      h('dl', { class: 'kv' },
        h('dt', null, term('defensive_line', 'Defensive line')), h('dd', null, num(d.lines.def)),
        h('dt', null, term('midfield_line', 'Midfield line')), h('dd', null, num(d.lines.mid)),
        h('dt', null, term('attack_line', 'Attack line')), h('dd', null, num(d.lines.att)),
        h('dt', null, term('length', 'Team length')), h('dd', null, num(sh.length)),
        h('dt', null, term('width', 'Team width')), h('dd', null, num(sh.width)),
        h('dt', null, term('compactness', 'Compactness')), h('dd', null, pct(sh.compact)))]);
}

export async function render({ load }) {
  const [summary, pos] = await Promise.all([load('summary'), load('positions')]);
  const teams = summary.teams, named = pos.windows.filter(w => w.kind !== 'slide'), slides = pos.windows.filter(w => w.kind === 'slide');
  if (!pos.data[ui.win]) ui = { win: 'full', team: 'both' };

  const svg = pitchSvg('Average player positions and defensive, midfield and attack lines');
  const layer = s('g'); svg.append(layer);
  const shapes = h('div', { class: 'grid2' });
  const live = h('p', { class: 'visually-hidden', 'aria-live': 'polite' });
  const slider = h('input', { type: 'range', id: 'win-slider', min: 0, max: slides.length - 1, step: 1, value: 0, 'aria-label': 'Move the time window through the match' });
  const sliderLabel = h('output', { for: 'win-slider', class: 'muted' });
  const winBtns = named.map(w => h('button', { type: 'button', class: 'btn', onclick: () => { ui.win = w.id; paint(); } }, w.label));
  const teamBtns = [['both', 'Both teams'], ['home', teams.home.name], ['away', teams.away.name]].map(([k, l]) =>
    h('button', { type: 'button', class: 'btn', onclick: () => { ui.team = k; paint(); } }, l));

  slider.addEventListener('input', () => { ui.win = slides[+slider.value].id; paint(); });

  function paint() {
    const w = pos.windows.find(x => x.id === ui.win), d = pos.data[ui.win];
    winBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(named[i].id === ui.win)));
    teamBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(['both', 'home', 'away'][i] === ui.team)));
    const idx = slides.findIndex(x => x.id === ui.win);
    if (idx >= 0) slider.value = idx;
    slider.setAttribute('aria-valuetext', `${w.label}`);
    sliderLabel.textContent = w.kind === 'slide' ? `Minutes ${w.start}–${w.end}` : `${w.label} (minutes ${w.start}–${w.end})`;
    live.textContent = `Showing ${w.label}`;

    clear(layer);
    for (const side of ['home', 'away']) {
      if (ui.team !== 'both' && ui.team !== side) continue;
      const color = side === 'home' ? 'var(--home)' : 'var(--away)', t = d[side];
      Object.entries(t.lines).forEach(([k, x], row) => {
        if (x == null) return;
        const lx = side === 'home' ? x : 120 - x;
        const ly = side === 'home' ? 3.4 + row * 3.1 : 76.6 - row * 3.1;   // one label row per line so they never collide
        layer.append(s('line', { x1: lx, y1: 0, x2: lx, y2: 80, stroke: color, 'stroke-width': .5, 'stroke-dasharray': '2 1.6', opacity: .85 }),
          s('text', { x: lx, y: ly, 'text-anchor': 'middle', fill: color, stroke: '#fff', 'stroke-width': .9, 'paint-order': 'stroke', 'font-size': 2.2, 'font-weight': 700 }, `${LINE_LABEL[k]} ${num(x)}`));
      });
      for (const p of t.players) {
        const g = s('g', { tabindex: 0, role: 'img', 'aria-label': `${p.name}, ${ROLE[p.role] || 'player'}, ${p.n} touches, average position ${p.x}, ${p.y}` },
          s('title', null, `${p.name} (${ROLE[p.role] || 'player'}) · ${p.n} touches`), marker(side, p.x, p.y, 2.7, p.jersey));
        layer.append(g);
      }
    }
    clear(shapes).append(...['home', 'away'].filter(k => ui.team === 'both' || ui.team === k).map(k => shapeCard(k, teams[k], d[k])));
    shapes.style.gridTemplateColumns = ui.team === 'both' ? '' : '1fr';
  }
  paint();

  return h('div', null,
    h('h1', { tabindex: '-1' }, 'Where each team stood'),
    h('p', { class: 'muted' }, 'Each dot is a player\'s average position in the chosen time window. The dashed lines are the average height of the back, middle and front groups. ',
      'Positions come from where players touched the ball, so they lean towards where the team had the ball; this is approximate and not full player tracking.'),
    h('div', { class: 'card' },
      h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Choose a period' }, winBtns),
      h('div', { class: 'slider-row' }, h('label', { for: 'win-slider' }, 'Time window'), slider, h('span'), sliderLabel),
      h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Choose teams' }, teamBtns),
      h('div', { class: 'pitch-wrap' }, svg), live,
      h('div', { class: 'legend' },
        h('span', { class: 'item' }, h('i', { class: 'swatch home' }), `${teams.home.name} (circles) attack to the right →`),
        h('span', { class: 'item' }, h('i', { class: 'swatch away' }), `← ${teams.away.name} (squares) attack to the left`),
        h('span', { class: 'item' }, 'Numbers are shirt numbers. Line labels show units from each team\'s own goal.'))),
    shapes);
}

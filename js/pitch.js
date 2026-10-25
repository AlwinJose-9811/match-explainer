// SVG pitch factory (120 x 80 viewBox, StatsBomb units) and the Pitch page: average positions, lines, shape, player panel.
import { h, s, clear, num, pct } from './dom.js';
import { term } from './glossary.js';
import { stage } from './stage.js';

/** Floodlit pitch: mowing stripes, glowing white lines, corner arcs and goals with nets. Home attacks right. */
export function pitchSvg(label) {
  const line = (d, w = .42) => [s('path', { d, class: 'glow', fill: 'none', stroke: '#fff', 'stroke-width': w * 3.4, opacity: .12 }),
    s('path', { d, class: 'mark', fill: 'none', stroke: '#F6FBF2', 'stroke-width': w, 'stroke-linejoin': 'round' })];
  const stripes = Array.from({ length: 12 }, (_, i) => s('rect', { x: i * 10, y: 0, width: 10, height: 80, fill: i % 2 ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.075)' }));
  const net = (x0, x1) => s('g', { class: 'net' }, s('rect', { x: Math.min(x0, x1), y: 36, width: Math.abs(x1 - x0), height: 8, fill: 'rgba(255,255,255,.1)', stroke: '#fff', 'stroke-width': .25 }),
    ...Array.from({ length: 4 }, (_, i) => s('line', { x1: x0 + ((x1 - x0) * (i + 1)) / 5, y1: 36, x2: x0 + ((x1 - x0) * (i + 1)) / 5, y2: 44, stroke: '#fff', 'stroke-width': .1, opacity: .5 })),
    ...Array.from({ length: 6 }, (_, i) => s('line', { x1: x0, y1: 37.1 + i * 1.15, x2: x1, y2: 37.1 + i * 1.15, stroke: '#fff', 'stroke-width': .1, opacity: .5 })));
  return s('svg', { class: 'pitch', viewBox: '0 0 120 80', role: 'img', 'aria-label': label, preserveAspectRatio: 'xMidYMid meet' },
    ...stripes,
    line('M0 0H120V80H0Z'), line('M60 0V80'), line('M60 30a10 10 0 1 0 .01 0Z'),
    line('M0 18H18V62H0'), line('M120 18H102V62H120'), line('M0 30H6V50H0'), line('M120 30H114V50H120'),
    line('M18 32A10 10 0 0 1 18 48'), line('M102 32A10 10 0 0 0 102 48'),
    line('M1 0A1 1 0 0 1 0 1', .3), line('M119 0A1 1 0 0 0 120 1', .3), line('M0 79A1 1 0 0 1 1 80', .3), line('M120 79A1 1 0 0 0 119 80', .3),
    s('circle', { cx: 60, cy: 40, r: .55, fill: '#F6FBF2' }), s('circle', { cx: 12, cy: 40, r: .5, fill: '#F6FBF2' }), s('circle', { cx: 108, cy: 40, r: .5, fill: '#F6FBF2' }),
    net(0, -2.8), net(120, 122.8));
}

/** A team marker: circle for home, rounded square for away, with a ground shadow, a highlight and an optional number. */
export function marker(side, x, y, r, text) {
  const home = side === 'home', fill = home ? 'var(--home)' : 'var(--away)';
  return [
    s('ellipse', { cx: x + r * .35, cy: y + r * .85, rx: r * 1.05, ry: r * .5, fill: '#000', opacity: .38 }),
    home ? s('circle', { cx: x, cy: y, r, fill, stroke: '#fff', 'stroke-width': .45 })
      : s('rect', { x: x - r, y: y - r, width: 2 * r, height: 2 * r, rx: r * .28, fill, stroke: '#fff', 'stroke-width': .45 }),
    s('ellipse', { cx: x - r * .25, cy: y - r * .45, rx: r * .55, ry: r * .28, fill: '#fff', opacity: .22 }),
    text != null ? s('text', { x, y: y + r * .38, 'text-anchor': 'middle', fill: '#fff', stroke: 'rgba(0,0,0,.5)', 'stroke-width': r * .16, 'paint-order': 'stroke',
      'font-size': r * 1.05, 'font-weight': 800, 'pointer-events': 'none' }, text) : null];
}

const ROLE = { GK: 'goalkeeper', DEF: 'defender', MID: 'midfielder', ATT: 'forward' };
const ROLE_ORDER = { GK: 0, DEF: 1, MID: 2, ATT: 3 };
const LINE_LABEL = { def: 'Back', mid: 'Mid', att: 'Front' };
let ui = { win: 'full', team: 'both', panel: 'home', hl: null };

const token = (side, text) => h('span', { class: `tok ${side}`, 'aria-hidden': 'true' }, text == null ? '' : String(text));

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
  if (!pos.data[ui.win]) ui = { win: 'full', team: 'both', panel: 'home', hl: null };

  const svg = pitchSvg('Average player positions and defensive, midfield and attack lines');
  const layer = s('g'), hlLayer = s('g');
  svg.append(layer, hlLayer);
  const st = stage(svg);
  const shapes = h('div', { class: 'grid2' });
  const caption = h('span', { class: 'pill', 'aria-live': 'polite' });
  st.hud.prepend(caption);
  const plist = h('ul', { class: 'plist' });
  const tabs = ['home', 'away'].map(k => h('button', { type: 'button', class: 'tab', onclick: () => { ui.panel = k; if (ui.team !== 'both') ui.team = k; paint(); } }, h('span', { class: `swatch ${k}` }), ' ', teams[k].name));
  const slider = h('input', { type: 'range', id: 'win-slider', min: 0, max: slides.length - 1, step: 1, value: 0, 'aria-label': 'Move the time window through the match' });
  const sliderLabel = h('output', { for: 'win-slider', class: 'muted' });
  const winBtns = named.map(w => h('button', { type: 'button', class: 'btn', onclick: () => { ui.win = w.id; paint(); } }, w.label));
  const teamBtns = [['both', 'Both teams'], ['home', teams.home.name], ['away', teams.away.name]].map(([k, l]) =>
    h('button', { type: 'button', class: 'btn', onclick: () => { ui.team = k; if (k !== 'both') ui.panel = k; paint(); } }, l));

  slider.addEventListener('input', () => { ui.win = slides[+slider.value].id; paint(); });

  function highlight() {
    clear(hlLayer);
    if (!ui.hl) return;
    const [side, id] = ui.hl.split(':'), p = pos.data[ui.win][side].players.find(x => String(x.id) === id);
    if (!p) return;
    hlLayer.append(s('circle', { cx: p.x, cy: p.y, r: 4.6, fill: 'none', stroke: '#C9E265', 'stroke-width': .7 }),
      s('text', { x: p.x, y: p.y - 6, 'text-anchor': 'middle', fill: '#F4EFD8', stroke: 'rgba(4,20,11,.9)', 'stroke-width': 1, 'paint-order': 'stroke', 'font-size': 2.6, 'font-weight': 800 }, p.name));
  }

  function panel(d) {
    const side = ui.panel, players = [...d[side].players].sort((a, b) => ROLE_ORDER[a.role] - ROLE_ORDER[b.role] || b.n - a.n), most = Math.max(1, ...players.map(p => p.n));
    tabs.forEach((b, i) => b.setAttribute('aria-pressed', String(['home', 'away'][i] === side)));
    clear(plist).append(...(players.length ? players.map(p => {
      const key = `${side}:${p.id}`, row = h('button', { type: 'button', class: 'prow', 'aria-label': `${p.name}, ${ROLE[p.role] || 'player'}, ${p.n} touches`, title: p.name },
        token(side, p.jersey), h('span', { class: 'pname' }, p.name), h('span', { class: 'role' }, p.role || '–'),
        h('span', { class: 'tbar', 'aria-hidden': 'true' }, h('i', { style: `width:${Math.round(100 * p.n / most)}%` })), h('b', null, String(p.n)));
      for (const ev of ['mouseenter', 'focus']) row.addEventListener(ev, () => { ui.hl = key; highlight(); });
      for (const ev of ['mouseleave', 'blur']) row.addEventListener(ev, () => { ui.hl = null; highlight(); });
      return h('li', null, row);
    }) : [h('li', { class: 'muted' }, 'Not enough touches in this window.')]));
  }

  function paint() {
    const w = pos.windows.find(x => x.id === ui.win), d = pos.data[ui.win];
    winBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(named[i].id === ui.win)));
    teamBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(['both', 'home', 'away'][i] === ui.team)));
    const idx = slides.findIndex(x => x.id === ui.win);
    if (idx >= 0) slider.value = idx;
    slider.setAttribute('aria-valuetext', `${w.label}`);
    sliderLabel.textContent = w.kind === 'slide' ? `Minutes ${w.start}–${w.end}` : `${w.label} (minutes ${w.start}–${w.end})`;
    caption.textContent = `${w.label} · minutes ${w.start}–${w.end}`;

    clear(layer);
    for (const side of ['home', 'away']) {
      if (ui.team !== 'both' && ui.team !== side) continue;
      const color = side === 'home' ? 'var(--home)' : 'var(--away)', t = d[side];
      Object.entries(t.lines).forEach(([k, x], row) => {
        if (x == null) return;
        const lx = side === 'home' ? x : 120 - x;
        const ly = side === 'home' ? 3.4 + row * 3.1 : 76.6 - row * 3.1;   // one label row per line so they never collide
        layer.append(s('line', { x1: lx, y1: 0, x2: lx, y2: 80, stroke: color, 'stroke-width': .5, 'stroke-dasharray': '2 1.6', opacity: .9 }),
          s('text', { x: lx, y: ly, 'text-anchor': 'middle', fill: '#F4EFD8', stroke: 'rgba(4,20,11,.9)', 'stroke-width': .9, 'paint-order': 'stroke', 'font-size': 2.2, 'font-weight': 700 }, `${LINE_LABEL[k]} ${num(x)}`));
      });
      for (const p of t.players) {
        layer.append(s('g', { tabindex: 0, role: 'img', 'aria-label': `${p.name}, ${ROLE[p.role] || 'player'}, ${p.n} touches, average position ${p.x}, ${p.y}` },
          s('title', null, `${p.name} (${ROLE[p.role] || 'player'}) · ${p.n} touches`), marker(side, p.x, p.y, 2.7, p.jersey)));
      }
    }
    ui.hl = null; highlight();
    panel(d);
    clear(shapes).append(...['home', 'away'].filter(k => ui.team === 'both' || ui.team === k).map(k => shapeCard(k, teams[k], d[k])));
    shapes.style.gridTemplateColumns = ui.team === 'both' ? '' : '1fr';
  }
  paint();

  return h('div', null,
    h('h1', { tabindex: '-1' }, 'Where each team stood'),
    h('p', { class: 'muted lede' }, 'Each token is a player\'s average position in the chosen time window. The dashed lines are the average height of the back, middle and front groups. ',
      'Positions come from where players touched the ball, so they lean towards where the team had the ball; this is approximate and not full player tracking.'),
    h('div', { class: 'card toolbar' },
      h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Choose a period' }, winBtns),
      h('div', { class: 'slider-row' }, h('label', { for: 'win-slider' }, 'Time window'), slider, h('span'), sliderLabel),
      h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Choose teams' }, teamBtns)),
    h('div', { class: 'split' },
      h('div', null, st.node,
        h('div', { class: 'legend' },
          h('span', { class: 'item' }, h('i', { class: 'swatch home' }), `${teams.home.name} (circles) attack to the right →`),
          h('span', { class: 'item' }, h('i', { class: 'swatch away' }), `← ${teams.away.name} (squares) attack to the left`),
          h('span', { class: 'item' }, 'Numbers are shirt numbers. Line labels show units from each team\'s own goal.'))),
      h('aside', { class: 'card panel', 'aria-label': 'Players in this window' },
        h('h2', null, 'Players in this window'), h('div', { class: 'tabs', role: 'group', 'aria-label': 'Choose a team' }, tabs), plist,
        h('p', { class: 'muted small' }, 'Hover or tab to a row to find the player on the pitch. Touches = on-ball actions used for the average position.'))),
    shapes);
}

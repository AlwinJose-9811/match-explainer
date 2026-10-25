// Shots and xG page: shot map (marker size = xG, goals outlined) plus an accessible table of every shot.
import { h, s, clear, num } from './dom.js';
import { term } from './glossary.js';
import { pitchSvg, marker } from './pitch.js';
import { stage } from './stage.js';

let ui = { team: 'both', goalsOnly: false };
const xgOf = sh => sh.xg_model ?? sh.xg_statsbomb ?? 0;
const describe = (sh, team) => {
  const res = sh.is_goal ? 'GOAL' : (sh.outcome || 'shot');
  return `${sh.clock} · ${sh.player || team} (${team}) · ${res}${sh.is_penalty ? ' (penalty)' : ''} · xG ${num(sh.xg_model, 2)}`
    + (sh.xg_statsbomb != null ? ` (StatsBomb ${num(sh.xg_statsbomb, 2)})` : '');
};

export async function render({ load }) {
  const [summary, data] = await Promise.all([load('summary'), load('shots')]);
  const teams = summary.teams, shots = data.shots;
  const svg = pitchSvg('Shot map: each marker is a shot, larger means a better chance');
  const layer = s('g'); svg.append(layer);
  const st = stage(svg);
  const info = h('p', { class: 'shotinfo', 'aria-live': 'polite' }, 'Hover over or tab to a shot to see who took it and how good the chance was.');
  const totals = h('div', { class: 'grid2' });
  const tbody = h('tbody');
  const teamBtns = [['both', 'Both teams'], ['home', teams.home.name], ['away', teams.away.name]].map(([k, l]) =>
    h('button', { type: 'button', class: 'btn', onclick: () => { ui.team = k; paint(); } }, l));
  const goalsBtn = h('button', { type: 'button', class: 'btn', onclick: () => { ui.goalsOnly = !ui.goalsOnly; paint(); } }, 'Goals only');

  function paint() {
    teamBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(['both', 'home', 'away'][i] === ui.team)));
    goalsBtn.setAttribute('aria-pressed', String(ui.goalsOnly));
    const shown = shots.filter(x => (ui.team === 'both' || x.team === ui.team) && (!ui.goalsOnly || x.is_goal) && x.x != null);
    clear(layer);
    for (const sh of [...shown].sort((a, b) => xgOf(b) - xgOf(a))) {   // small markers drawn last, on top
      const side = sh.team, px = side === 'home' ? sh.x : 120 - sh.x, py = side === 'home' ? sh.y : 80 - sh.y;
      const r = .9 + 4.2 * Math.sqrt(xgOf(sh)), label = describe(sh, teams[side].name);
      const g = s('g', { tabindex: 0, role: 'img', 'aria-label': label, opacity: sh.is_goal ? 1 : .55 },
        s('title', null, label), marker(side, px, py, r, null));
      if (sh.is_goal) g.prepend(s('circle', { cx: px, cy: py, r: r + 1.4, fill: 'none', stroke: '#FFD84A', 'stroke-width': .7 }));
      for (const ev of ['mouseenter', 'focus']) g.addEventListener(ev, () => { info.textContent = label; });
      layer.append(g);
    }
    clear(totals).append(...['home', 'away'].filter(k => ui.team === 'both' || ui.team === k).map(k => {
      const mine = shots.filter(x => x.team === k);
      return h('div', { class: 'card' }, h('h3', null, h('span', { class: `chip ${k}` }, teams[k].name)),
        h('dl', { class: 'kv' },
          h('dt', null, term('xg_model', 'xG (our model)')), h('dd', null, num(summary.stats[k].xg_model, 2)),
          h('dt', null, term('xg_statsbomb', 'xG (StatsBomb)')), h('dd', null, num(summary.stats[k].xg_statsbomb, 2)),
          h('dt', null, 'Shots'), h('dd', null, String(mine.length)),
          h('dt', null, 'Goals'), h('dd', null, String(mine.filter(x => x.is_goal).length))));
    }));
    totals.style.gridTemplateColumns = ui.team === 'both' ? '' : '1fr';
    clear(tbody).append(...shown.map(sh => h('tr', null,
      h('td', null, sh.clock), h('td', null, h('i', { class: `swatch ${sh.team}` }), ' ', teams[sh.team].name),
      h('td', null, sh.player || ''), h('td', null, (sh.is_goal ? 'Goal' : sh.outcome || '') + (sh.is_penalty ? ' (penalty)' : '')),
      h('td', { class: 'num' }, num(sh.xg_model, 2)), h('td', { class: 'num' }, num(sh.xg_statsbomb, 2)))));
  }
  paint();

  return h('div', null,
    h('h1', { tabindex: '-1' }, 'Shots and chance quality'),
    h('p', { class: 'muted' }, 'Every shot in normal time and extra time. A bigger marker means a better chance (higher ', term('xg_model', 'xG'), '). Outlined, solid markers are goals; faded markers did not score. The penalty shootout is not shown.'),
    h('div', { class: 'card' },
      h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Filter shots' }, teamBtns, goalsBtn),
      st.node, info,
      h('div', { class: 'legend' },
        h('span', { class: 'item' }, h('i', { class: 'swatch home' }), `${teams.home.name} (circles) attack right →`),
        h('span', { class: 'item' }, h('i', { class: 'swatch away' }), `← ${teams.away.name} (squares) attack left`),
        h('span', { class: 'item' }, 'Penalties are shown at the spot with the average penalty chance.'))),
    totals,
    h('section', { class: 'card', 'aria-labelledby': 'shot-table-h' },
      h('h2', { id: 'shot-table-h' }, 'All shots'),
      h('div', { class: 'scroll' }, h('table', { class: 'plain' },
        h('thead', null, h('tr', null, ['Time', 'Team', 'Player', 'Result'].map(t => h('th', { scope: 'col' }, t)),
          h('th', { scope: 'col', class: 'num' }, term('xg_model', 'xG')), h('th', { scope: 'col', class: 'num' }, term('xg_statsbomb', 'StatsBomb')))),
        tbody))));
}

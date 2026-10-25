// Key moments page: moment list on the left, replay + plain-English explanation on the right.
import { h, s, clear, num } from './dom.js';
import { term } from './glossary.js';
import { listenButton, stopSpeaking } from './speech.js';
import { createReplay } from './replay.js';
import { pitchSvg } from './pitch.js';
import { stage } from './stage.js';

const KIND = m => ({ goal: m.is_penalty ? 'Penalty goal' : 'Goal', penalty: 'Missed penalty', red_card: 'Red card', own_goal: 'Own goal', shot: 'Big chance' })[m.type];
let ui = { goalsOnly: false };
let replay = null;

function penaltyCard(m, teams) {
  const svg = pitchSvg(`Penalty at ${m.clock}`);
  svg.append(
    s('defs', null, s('marker', { id: 'ah-pen', viewBox: '0 0 6 6', refX: 5, refY: 3, markerWidth: 4, markerHeight: 4, orient: 'auto' }, s('path', { d: 'M0 0 L6 3 L0 6 z', fill: '#FFD84A' }))),
    s('line', { x1: 108, y1: 40, x2: 119.4, y2: m.is_goal ? 40 : 37, stroke: 'rgba(4,20,11,.72)', 'stroke-width': 2.4, 'stroke-linecap': 'round' }),
    s('line', { x1: 108, y1: 40, x2: 119.4, y2: m.is_goal ? 40 : 37, stroke: '#FFD84A', 'stroke-width': 1.2, 'stroke-linecap': 'round', 'marker-end': 'url(#ah-pen)' }),
    s('circle', { cx: 108, cy: 40, r: 1.6, fill: '#F7F4E8', stroke: '#16301F', 'stroke-width': .25 }),
    s('text', { x: 108, y: 47, 'text-anchor': 'middle', 'font-size': 2.6, fill: '#F4EFD8', stroke: 'rgba(4,20,11,.9)', 'stroke-width': 1, 'paint-order': 'stroke', 'font-weight': 800 }, 'Penalty spot'));
  const stg = stage(svg);
  stg.hud.prepend(h('p', { class: 'pill' }, `A penalty has no build-up: ${teams[m.team].name} take a free shot from the spot, with only the goalkeeper to beat.`));
  return h('div', { class: 'replay' }, stg.node);
}

function detail(m, ctx) {
  const { teams, names } = ctx, nm = n => (n ? names[n] || n : n), exp = m.explanation;
  if (replay) replay.destroy();
  replay = null;
  let visual;
  if (m.sequence.length) { replay = createReplay(m, ctx); visual = replay.node; }
  else if (m.is_penalty) visual = penaltyCard(m, teams);
  else visual = h('div', { class: 'card redcard' }, h('span', { class: 'card-icon', 'aria-hidden': 'true' }), h('p', null, `${nm(m.player)} (${teams[m.team].name}) at ${m.clock}`));
  const listen = listenButton(() => exp.speech || `${exp.text} ${exp.why}`, 'Listen to the commentary', exp.audio);
  return h('div', null,
    h('h2', { id: 'moment-h', tabindex: '-1' }, `${KIND(m)} · ${m.clock}`),
    h('p', { class: 'muted' }, h('i', { class: `swatch ${m.team}` }), ` ${nm(m.player) || teams[m.team].name} for ${teams[m.team].name}`,
      m.xg_model != null ? [' · chance quality ', h('strong', null, `${num(m.xg_model, 2)} `), term('xg_model', 'xG'), ` (StatsBomb ${num(m.xg_statsbomb, 2)})`] : null),
    visual,
    h('section', { class: 'card', 'aria-labelledby': 'why-h' },
      h('h3', { id: 'why-h' }, 'What happened'), h('p', null, exp.text),
      h('h3', null, 'Why it worked'), h('p', null, exp.why),
      h('p', null, h('span', { class: 'badge' }, term('automated', exp.label)), ' ', listen)));
}

export async function render({ load, matchId }) {
  const [summary, data] = await Promise.all([load('summary'), load('moments')]);
  const ctx = { teams: summary.teams, names: data.names || {} };
  const all = data.moments, goals = all.filter(m => m.is_goal);
  const wanted = new URLSearchParams(location.hash.split('?')[1] || '').get('mo');
  let sel = all.find(m => m.id === wanted) || goals.find(m => m.sequence.length) || all[0];
  if (!all.length) return h('div', null, h('h1', { tabindex: '-1' }, 'Key moments'), h('div', { class: 'card' }, 'No key moments were detected for this match.'));

  const list = h('ul', { class: 'mlist', 'aria-label': 'Key moments' });
  const pane = h('div', { class: 'mpane' });
  const filterBtns = [[false, `All moments (${all.length})`], [true, `Goals only (${goals.length})`]].map(([v, l]) =>
    h('button', { type: 'button', class: 'btn', onclick: () => { ui.goalsOnly = v; if (v && !sel.is_goal) sel = goals[0]; paintList(); show(sel, false); } }, l));

  function paintList() {
    filterBtns.forEach((b, i) => b.setAttribute('aria-pressed', String([false, true][i] === ui.goalsOnly)));
    clear(list).append(...all.filter(m => !ui.goalsOnly || m.is_goal).map(m => h('li', null,
      h('button', { type: 'button', class: 'mitem', 'aria-current': m.id === sel.id ? 'true' : null, onclick: () => show(m, true) },
        h('span', { class: 'mclock' }, m.clock), h('span', { class: 'mbody' }, h('strong', null, KIND(m)),
          h('span', null, h('i', { class: `swatch ${m.team}` }), ' ', ctx.names[m.player] || m.player || ctx.teams[m.team].name))))));
  }
  function show(m, focus) {
    stopSpeaking(); sel = m; paintList();
    clear(pane).append(detail(m, ctx));
    history.replaceState(null, '', `#moments?m=${matchId}&mo=${m.id}`);
    if (focus) pane.querySelector('#moment-h')?.focus({ preventScroll: false });
  }
  paintList(); show(sel, false);

  return h('div', null,
    h('h1', { tabindex: '-1' }, 'Key moments, replayed'),
    h('p', { class: 'muted' }, 'Pick a moment to watch the move that led to it and read why it worked. Goals from penalties have no build-up, so they are shown as a simple card.'),
    h('div', { class: 'moments' },
      h('aside', null, h('div', { class: 'btn-row', role: 'group', 'aria-label': 'Filter moments' }, filterBtns), list),
      pane));
}

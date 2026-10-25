// Summary page: scoreline, possession, plain-English stat table, match story.
import { h, pct, num } from './dom.js';
import { term } from './glossary.js';
import { listenButton } from './speech.js';

const ROWS = [
  { key: 'shots', label: 'Shots', val: s => s.shots },
  { key: 'on_target', label: 'Shots on target', val: s => s.on_target },
  { key: 'passes', label: 'Passes completed', val: s => s.passes_completed, sub: s => `of ${s.passes}` },
  { key: 'pass_accuracy', label: 'Pass accuracy', val: s => pct(s.pass_accuracy), raw: s => s.pass_accuracy },
  { key: 'xg_model', label: 'xG (our model)', val: s => num(s.xg_model, 2), raw: s => s.xg_model ?? 0 },
  { key: 'xg_statsbomb', label: 'xG (StatsBomb)', val: s => num(s.xg_statsbomb, 2), raw: s => s.xg_statsbomb },
  { key: 'fouls', label: 'Fouls', val: s => s.fouls },
  { key: 'corners', label: 'Corners', val: s => s.corners },
  { key: 'yellow', label: 'Yellow cards', val: s => s.yellow },
  { key: 'red', label: 'Red cards', val: s => s.red },
];

function statRow(row, hs, as) {
  const raw = row.raw || row.val;
  const a = Number(raw(hs)), b = Number(raw(as)), max = Math.max(a, b, 1e-9);
  const cell = (side, st, v) => h('td', { class: side },
    h('div', { class: 'val' }, row.val(st)), row.sub ? h('div', { class: 'sub' }, row.sub(st)) : null,
    h('div', { class: 'bar', 'aria-hidden': 'true' }, h('i', { style: `width:${(100 * v / max).toFixed(0)}%` })));
  return h('tr', null, cell('h', hs, a), h('th', { scope: 'row' }, term(row.key, row.label)), cell('a', as, b));
}

export async function render({ load }) {
  const s = await load('summary');
  const { home, away } = s.teams, sc = s.score;
  const meta = [s.competition + ' ' + s.season, s.stage, s.date].filter(Boolean).join(' · ');
  const story = s.story;
  const listen = story ? listenButton(() => story.speech || story.text, 'Listen to the story') : null;

  return h('div', null,
    h('section', { class: 'card center', 'aria-labelledby': 'score-h' },
      h('p', { class: 'eyebrow' }, meta),
      h('h1', { id: 'score-h', tabindex: '-1', class: 'visually-hidden' }, `${home.name} ${sc.home}, ${away.name} ${sc.away}`),
      h('div', { class: 'scoreline', 'aria-hidden': 'true' },
        h('span', { class: 'team' }, h('i', { class: 'swatch home' }), home.name),
        h('span', { class: 'score' }, `${sc.home}–${sc.away}`),
        h('span', { class: 'team' }, away.name, h('i', { class: 'swatch away' }))),
      sc.shootout ? h('p', null, h('strong', null, `Penalty shootout ${sc.shootout.home}–${sc.shootout.away}`)) : null,
      sc.note ? h('p', { class: 'note' }, sc.note) : null),

    h('section', { class: 'card', 'aria-labelledby': 'poss-h' },
      h('h2', { id: 'poss-h' }, term('possession', 'Possession')),
      h('div', { class: 'poss', role: 'img', 'aria-label': `Possession: ${home.name} ${pct(s.possession.home)}, ${away.name} ${pct(s.possession.away)}` },
        h('span', { class: 'h', style: `width:${100 * s.possession.home}%` }, pct(s.possession.home)),
        h('span', { class: 'a', style: `width:${100 * s.possession.away}%` }, pct(s.possession.away))),
      h('p', { class: 'muted' }, `How it is measured: ${s.possession.method}. Each spell of play counts for the team that had the ball.`)),

    story ? h('section', { class: 'card', 'aria-labelledby': 'story-h' },
      h('h2', { id: 'story-h' }, 'Match story'),
      h('p', null, story.text),
      h('p', null, h('span', { class: 'badge' }, term('automated', story.label)), ' ', listen)) : null,

    h('section', { class: 'card', 'aria-labelledby': 'stats-h' },
      h('h2', { id: 'stats-h' }, 'The numbers, in plain English'),
      h('p', { class: 'muted' }, 'Hover over, tab to or tap any underlined label to see what it means.'),
      h('div', { class: 'scroll' }, h('table', { class: 'stats' },
        h('thead', null, h('tr', null,
          h('th', { scope: 'col' }, h('i', { class: 'swatch home' }), ' ', home.name),
          h('th', { scope: 'col' }, h('span', { class: 'visually-hidden' }, 'Statistic')),
          h('th', { scope: 'col' }, away.name, ' ', h('i', { class: 'swatch away' })))),
        h('tbody', null, ROWS.map(r => statRow(r, s.stats.home, s.stats.away))))),
      h('p', { class: 'muted' }, 'Everything covers normal time and extra time. The penalty shootout is reported separately above.')));
}

// App shell: hash router (#page?m=<matchId>), match picker, lazy data loading, friendly errors.
import { h, clear } from './dom.js';
import { load, matchFile, DataError } from './data.js';
import { stopSpeaking } from './speech.js';
import * as summary from './summary.js';
import * as pitch from './pitch.js';
import * as shots from './shots.js';
import * as glossary from './glossary.js';

const lazy = name => ({ render: async ctx => (await import(`./${name}.js`)).render(ctx) });

const PAGES = [
  { id: 'summary', title: 'Summary', mod: summary },
  { id: 'pitch', title: 'Pitch', mod: pitch },
  { id: 'moments', title: 'Key moments', mod: lazy('moments') },
  { id: 'shots', title: 'Shots & xG', mod: shots },
  { id: 'model', title: 'Model card', mod: lazy('model') },
  { id: 'glossary', title: 'Glossary', mod: { render: async () => glossary.render() } },
];

const view = document.getElementById('view');
const nav = document.getElementById('nav');
const picker = document.getElementById('match-picker');
let index = null;

function parseHash() {
  const [page, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const m = Number(new URLSearchParams(query).get('m'));
  return { page: PAGES.some(p => p.id === page) ? page : 'home', matchId: m || null };   // no hash (or an unknown one) = the landing page
}
const hashFor = (page, matchId) => `#${page}?m=${matchId}`;

function showError(e) {
  const file = e instanceof DataError ? e.file : null;
  clear(view).append(h('div', { class: 'error', role: 'alert' },
    h('h1', null, 'Something did not load'),
    file ? h('p', null, `The file `, h('code', null, `data/${file}`), ' could not be loaded.') : h('p', null, String(e && e.message || e)),
    h('p', null, 'If you opened this page by double-clicking the file, start the local server instead: ',
      h('code', null, 'python tasks.py serve'), ' and open http://localhost:8000. If you just rebuilt the data, run ',
      h('code', null, 'python tasks.py build'), ' first.')));
}

async function showLanding() {
  document.body.classList.add('is-landing');
  clear(nav);
  document.title = 'Match Explainer · See why the goal happened';
  try {
    clear(view).append(await (await import('./landing.js')).render({ index, load }));
    window.scrollTo(0, 0);
  } catch (e) { document.body.classList.remove('is-landing'); showError(e); }
}

async function route() {
  stopSpeaking();
  const { page, matchId } = parseHash();
  if (page === 'home') { await showLanding(); return; }
  document.body.classList.remove('is-landing');
  const id = matchId && index.matches.some(m => m.match_id === matchId) ? matchId : index.default;
  if (matchId !== id) { location.replace(hashFor(page, id)); return; }
  picker.value = String(id);
  clear(nav).append(...PAGES.map(p => h('a', { href: hashFor(p.id, id), 'aria-current': p.id === page ? 'page' : null }, p.title)));
  const def = PAGES.find(p => p.id === page);
  document.title = `${def.title} · Match Explainer`;
  try {
    const node = await def.mod.render({ matchId: id, load: name => matchFile(id, name), loadAny: load, index });
    clear(view).append(node);
    const hd = view.querySelector('h1');
    if (hd) { hd.tabIndex = -1; hd.focus({ preventScroll: true }); }
    window.scrollTo(0, 0);
  } catch (e) { showError(e); }
}

async function start() {
  try {
    index = await load('index.json');
  } catch (e) { showError(e); return; }
  clear(picker).append(...index.matches.map(m => h('option', { value: m.match_id }, `${m.label} (${m.score})`)));
  picker.addEventListener('change', () => { location.hash = hashFor(parseHash().page, picker.value); });
  window.addEventListener('hashchange', route);
  route();
}
start();

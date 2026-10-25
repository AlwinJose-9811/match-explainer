// Model card: what the xG model is, its data, features, honest metrics and limits (renders from xg_metrics.json).
import { h, num } from './dom.js';
import { term } from './glossary.js';

const FEATURE = {
  x: 'How far up the pitch the shot was taken', y_abs: 'How far the shot was from the centre line',
  dist: 'Distance to the middle of the goal', angle: 'How wide the goal looks from the shot (a bigger angle is easier)',
  under_pressure: 'A defender was pressing the shooter', first_time: 'Shot taken without controlling the ball first',
  has_ff: 'Whether positions of nearby players were recorded', is_open_goal: 'No goalkeeper or defender between the shooter and the goal',
  gk_dist: 'Distance to the goalkeeper', gk_off_centre: 'How far the goalkeeper stood from the centre of the goal',
  n_def_in_cone: 'Defenders in the triangle between the shooter and the posts', nearest_def_dist: 'Distance to the nearest outfield defender',
  body_part: 'Right foot, left foot, head or other', technique: 'Normal, volley, lob, overhead kick, and so on',
  play_pattern: 'How the move started: open play, corner, free kick, counter...', shot_type: 'Open play, free kick or corner shot',
};
const MODELS = [['baseline_constant', 'Guess the average chance every time'], ['baseline_distance_angle', 'Distance and angle only'],
  ['our_model', 'Our model (all features)'], ['statsbomb_xg', 'StatsBomb xG (richer, for comparison)']];

export async function render({ loadAny }) {
  const m = await loadAny('model/xg_metrics.json');
  const t = m.metrics_test, ours = t.our_model, base = t.baseline_distance_angle, sb = t.statsbomb_xg;
  const row = ([k, label]) => h('tr', { class: k === 'our_model' ? 'hl' : null },
    h('th', { scope: 'row' }, label), h('td', { class: 'num' }, num(t[k].log_loss, 3)), h('td', { class: 'num' }, num(t[k].brier, 3)),
    h('td', { class: 'num' }, num(t[k].roc_auc, 3)), h('td', { class: 'num' }, `${num(t[k].total_xg, 0)} of ${t[k].goals}`),
    h('td', { class: 'num' }, t[k].ece != null ? num(t[k].ece, 3) : '–'));
  const imp = m.permutation_importance.slice(0, 8), top = Math.max(...imp.map(i => i.log_loss_increase));

  return h('div', null,
    h('h1', { tabindex: '-1' }, 'Model card: how chance quality (xG) is calculated'),
    h('div', { class: 'card' }, h('h2', null, 'What it does'),
      h('p', null, 'The model looks at a shot at the moment it is taken and estimates the chance it becomes a goal, from 0 to 1. ',
        'It is a logistic regression: a simple, explainable formula that weighs the features below. It explains chance quality; it does not predict who wins matches and is not for betting.'),
      h('p', null, h('span', { class: 'badge' }, term('automated', 'Automated analysis')), ` Trained ${m.date} (seed ${m.seed}).`)),

    h('div', { class: 'card' }, h('h2', null, 'Data'),
      h('p', null, `Trained on ${m.train.kept.toLocaleString()} shots from ${m.train.matches} matches (${m.train.competitions.join(', ')}), then tested on `,
        h('strong', null, `${m.test.kept.toLocaleString()} shots from ${m.test.matches} matches of ${m.test.competitions.join(', ')}`),
        ', a competition the model never saw. The 2022 World Cup (the matches on this site) was never used for training.'),
      h('p', { class: 'muted' }, `Left out of training: ${m.train.excluded_penalties} penalties (they get a fixed ${num(m.penalty.rate * 100, 0)}% chance, the rate in the training data), shootout kicks, own goals and shots with no location. `
        + `Overall about ${num(m.train.goal_rate * 100, 1)}% of shots were goals. Data: StatsBomb open data.`)),

    h('div', { class: 'card' }, h('h2', null, 'How well it works (on the test competition)'),
      h('div', { class: 'scroll' }, h('table', { class: 'plain' },
        h('thead', null, h('tr', null, h('th', null, 'Model'), h('th', { class: 'num' }, term('log_loss', 'Log loss')), h('th', { class: 'num' }, term('brier', 'Brier')),
          h('th', { class: 'num' }, term('roc_auc', 'AUC')), h('th', { class: 'num' }, 'Total xG vs goals'), h('th', { class: 'num' }, term('calibration', 'Calibration error')))),
        h('tbody', null, MODELS.map(row)))),
      h('p', null, `In plain words: lower log loss and Brier are better, higher AUC is better. Our model beats the distance-and-angle baseline (log loss ${num(ours.log_loss, 3)} against ${num(base.log_loss, 3)}) `
        + `but lands behind StatsBomb's own xG (${num(sb.log_loss, 3)}), which uses richer data. Across the test shots it expected ${num(ours.total_xg, 0)} goals and ${ours.goals} were scored.`)),

    h('div', { class: 'card' }, h('h2', null, term('calibration', 'Calibration'), ': do the percentages mean what they say?'),
      h('img', { src: 'data/model/xg_calibration.png', alt: 'Calibration plot: predicted chance against how often shots were goals, for our model and StatsBomb, with a histogram of predictions', style: 'max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px' }),
      h('p', { class: 'muted' }, 'Points near the dashed diagonal mean the model is honest: shots rated 20% are goals about 20% of the time. There are few shots above 40%, so the top end is less certain.'),
      h('details', null, h('summary', null, 'Same data as a table'),
        h('table', { class: 'plain' }, h('thead', null, h('tr', null, h('th', null, 'Predicted'), h('th', null, 'Actually scored'))),
          h('tbody', null, m.calibration_curve.map(p => h('tr', null, h('td', null, `${num(p.predicted * 100, 0)}%`), h('td', null, `${num(p.actual * 100, 0)}%`))))))),

    h('div', { class: 'card' }, h('h2', null, 'What the model looks at'),
      h('p', { class: 'muted' }, 'Only things known at the moment of the shot. It never sees whether the shot scored, where it ended up, or StatsBomb\'s own xG.'),
      h('dl', { class: 'gl' }, m.features.map(f => [h('dt', null, f), h('dd', null, FEATURE[f] || '')])),
      h('h3', null, 'What matters most'),
      h('ul', { class: 'bars' }, imp.map(i => h('li', null, h('span', null, i.feature), h('i', { style: `width:${Math.max(3, 100 * i.log_loss_increase / top)}%` }), h('b', null, num(i.log_loss_increase, 3))))),
      h('p', { class: 'muted' }, 'Bars show how much worse the model gets if that feature is scrambled (permutation importance on the test shots).')),

    h('div', { class: 'card' }, h('h2', null, 'Limits'),
      h('ul', null,
        h('li', null, 'Event data has no continuous tracking, so positions are averages and the tactical labels are approximate.'),
        h('li', null, 'The 360 snapshots show only players on the TV picture, so the real last defender is sometimes missing.'),
        h('li', null, 'Penalties use one fixed chance for every kick; the model does not judge the taker or the goalkeeper.'),
        h('li', null, 'Training was on league seasons (including women\'s and La Liga matches that involve one club), tested on one tournament; other competitions could differ.'),
        h('li', null, 'xG measures chance quality, not skill: a low-xG goal can be luck, and a miss from a big chance can be a good save.'),
        h('li', null, 'All explanation text is automated and uses only facts from the data.')),
      h('p', { class: 'muted' }, 'Rebuild everything with ', h('code', null, 'python tasks.py train'), ' and ', h('code', null, 'python tasks.py build'), '.')));
}

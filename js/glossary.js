// Glossary data, hover/focus tooltips for terms, and the Glossary page.
import { h, clear } from './dom.js';

export const TERMS = {
  possession: ['Possession', 'Which team has the ball. Here it is the share of ball time: each spell of play counts for the team that had the ball, from its first to its last action.'],
  shots: ['Shots', 'Attempts to score, including ones that were blocked or missed. Penalty shootout kicks are not counted.'],
  on_target: ['Shots on target', 'Shots that were going into the goal unless the goalkeeper stopped them, or that scored.'],
  passes: ['Passes completed', 'Passes that reached a teammate, out of all passes attempted.'],
  pass_accuracy: ['Pass accuracy', 'The share of attempted passes that reached a teammate. Higher means safer passing, not necessarily better attacking.'],
  xg_model: ['xG, our model', 'Expected goals: the chance, from 0 to 1, that a shot becomes a goal. 0.30 means about 3 in 10 shots like it are scored. This one comes from the model trained for this project.'],
  xg_statsbomb: ['xG, StatsBomb', 'Expected goals as calculated by StatsBomb with extra information. Shown as a benchmark to compare with our model.'],
  fouls: ['Fouls', 'Rule breaks by a team, such as pushing or a late tackle, which give the other side a free kick or penalty.'],
  corners: ['Corners', 'Set pieces taken from the corner of the pitch after the defending team puts the ball over its own goal line.'],
  yellow: ['Yellow cards', 'Warnings from the referee. A second yellow card in one match becomes a red card.'],
  red: ['Red cards', 'A player sent off for serious foul play or a second yellow. The team plays on with one player fewer.'],
  defensive_line: ['Defensive line', 'The average position of a team\'s defenders. It is measured in units from their own goal (1 unit is about 1 yard, or 0.9 m): small means deep, large means far up the pitch.'],
  midfield_line: ['Midfield line', 'The average position of a team\'s midfielders, measured from their own goal.'],
  attack_line: ['Attack line', 'The average position of a team\'s forwards and wingers, measured from their own goal.'],
  length: ['Team length', 'The distance between a team\'s attack line and its defensive line. A short team is tightly packed.'],
  width: ['Team width', 'How far apart the team\'s widest players are, from side to side.'],
  compactness: ['Compactness', 'How close together a team\'s lines are, from 0 to 100 percent. Higher means defenders and forwards are closer, leaving smaller gaps.'],
  block: ['Block label', 'A plain label for how high the defence stands: "low block" is deep near their own goal, "mid block" is in between, "high line" is far up the pitch. The cut-offs come from the ten matches shown here, so the label is relative.'],
  build_up: ['Build-up', 'The passing sequence that leads to a shot.'],
  carry: ['Carry', 'A player running with the ball at their feet.'],
  key_pass: ['Key pass', 'The last pass before a shot.'],
  offside_line: ['Offside line', 'The position of the last defender (not counting the goalkeeper). An attacker level with or behind it when the ball is played is not offside.'],
  freeze_frame: ['Freeze frame (360 data)', 'The positions of the players visible on the TV camera at the instant of an event. Players outside the camera view are missing, so it never shows everyone.'],
  counter: ['Counter-attack', 'A fast attack straight after winning the ball, before the other team has got back into shape.'],
  rebound: ['Rebound', 'A shot that follows an earlier shot in the same move, often after the goalkeeper pushes the ball away.'],
  set_piece: ['Set piece', 'A restart such as a corner, free kick or throw-in.'],
  penalty: ['Penalty', 'A free shot from the spot, given for a foul inside the box. Most are scored (about 79 in 100 in our training data).'],
  shootout: ['Penalty shootout', 'The tie-break after extra time: each team takes five penalties in turn. It is shown separately and does not count as part of the match statistics.'],
  extra_time: ['Extra time', 'Two extra periods of 15 minutes played when a knockout match is level after 90 minutes.'],
  calibration: ['Calibration', 'Whether predicted chances match reality: shots predicted at 30 percent should be goals about 30 percent of the time.'],
  log_loss: ['Log loss', 'A score for how good predicted probabilities are, punishing confident wrong answers. Lower is better.'],
  brier: ['Brier score', 'The average squared gap between each predicted chance and what happened (1 for a goal, 0 for none). Lower is better.'],
  roc_auc: ['ROC AUC', 'How well the model ranks goals above non-goals: 0.5 is guessing, 1.0 is perfect.'],
  automated: ['Automated analysis', 'Text written by a program from the match data, not by a person. It only uses facts from the data and can still be incomplete.'],
  visible_players: ['Visible players only', 'The 360 data records only the players on the broadcast picture, so some players, and sometimes the real last defender, are missing.'],
};

let tipEl = null;
function tip() {
  if (!tipEl) {
    tipEl = h('div', { id: 'tip', role: 'tooltip', hidden: true });
    document.body.append(tipEl);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') hideTip(); });
  }
  return tipEl;
}
const hideTip = () => { if (tipEl) tipEl.hidden = true; };

function showTip(el, key) {
  const [name, help] = TERMS[key];
  const t = tip();
  t.replaceChildren(h('b', null, name), help);
  t.hidden = false;
  const r = el.getBoundingClientRect(), w = t.offsetWidth, ht = t.offsetHeight;
  const left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2));
  const top = r.bottom + ht + 12 < window.innerHeight ? r.bottom + 8 : Math.max(8, r.top - ht - 8);
  t.style.left = `${left}px`; t.style.top = `${top}px`;
}

/** A label with a dotted underline that explains itself on hover, focus or tap. */
export function term(key, label) {
  const [name, help] = TERMS[key];
  const el = h('button', { type: 'button', class: 'term', 'aria-label': `${label}. ${name}: ${help}` }, label);
  el.addEventListener('mouseenter', () => showTip(el, key));
  el.addEventListener('mouseleave', hideTip);
  el.addEventListener('focus', () => showTip(el, key));
  el.addEventListener('blur', hideTip);
  el.addEventListener('click', () => (tipEl && !tipEl.hidden ? hideTip() : showTip(el, key)));
  return el;
}

export function render() {
  const entries = Object.values(TERMS).sort((a, b) => a[0].localeCompare(b[0]));
  return h('div', null,
    h('h1', { tabindex: '-1' }, 'Glossary'),
    h('p', { class: 'muted' }, `${entries.length} terms used on this site, in plain English. Any underlined label elsewhere explains itself when you hover over it, tab to it or tap it.`),
    h('div', { class: 'card' }, h('dl', { class: 'gl' }, entries.map(([n, d]) => [h('dt', null, n), h('dd', null, d)]))));
}

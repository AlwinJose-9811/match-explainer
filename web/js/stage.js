// The "stage": a pitch SVG inside a stadium frame (crowd, advertising boards, floodlit turf), with an overlay layer for
// floating HTML cards positioned in pitch coordinates, a HUD row for captions, and an optional tilted 3D camera.
// The SVG keeps the 120 x 80 pitch frame, so every data point lands in the right place whether tilted or not.
import { h } from './dom.js';

/** Shared camera state: the 3D tilt stays on/off as you move between pages. */
export const camera = { tilt: false };

/** Wrap a pitch SVG. Returns { node, board, overlay, hud, tiltBtn }: put cards in `overlay`, captions in `hud`. */
export function stage(svg) {
  if (/tilt/.test(location.hash)) camera.tilt = true;   // "#...&tilt" opens the pages in the 3D view
  const overlay = h('div', { class: 'overlay' });
  const board = h('div', { class: 'board' }, svg, overlay);
  const hud = h('div', { class: 'hud' });
  const node = h('div', { class: 'stage', 'data-tilt': camera.tilt ? 'on' : 'off' },
    h('div', { class: 'crowd', 'aria-hidden': 'true' }),
    h('div', { class: 'ads', 'aria-hidden': 'true' }, Array.from({ length: 9 }, () => h('span', null, 'MATCH EXPLAINER'))),
    h('div', { class: 'turf' }, board));
  const tiltBtn = h('button', { type: 'button', class: 'btn tilt', 'aria-pressed': String(camera.tilt),
    'aria-label': 'Switch between the flat view and the tilted 3D view' }, '3D view');
  tiltBtn.addEventListener('click', () => {
    camera.tilt = !camera.tilt;
    node.dataset.tilt = camera.tilt ? 'on' : 'off';
    tiltBtn.setAttribute('aria-pressed', String(camera.tilt));
  });
  hud.append(tiltBtn);
  node.prepend(hud);
  return { node, board, overlay, hud, tiltBtn };
}

/** Pitch coordinates (0..120, 0..80) to CSS percentages inside the board, for positioning overlay cards. */
export const pct = (x, y) => ({ left: `${(x / 120) * 100}%`, top: `${(y / 80) * 100}%` });

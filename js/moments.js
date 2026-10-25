// Placeholder until Phase 7 (replay engine).
import { h } from './dom.js';

export async function render() {
  return h('div', null, h('h1', { tabindex: '-1' }, 'Key moments'),
    h('div', { class: 'card' }, h('p', null, 'Animated replays of the key moments arrive in the next build step.')));
}

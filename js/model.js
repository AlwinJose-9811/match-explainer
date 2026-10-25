// Placeholder until Phase 7 (model card).
import { h } from './dom.js';

export async function render() {
  return h('div', null, h('h1', { tabindex: '-1' }, 'Model card'),
    h('div', { class: 'card' }, h('p', null, 'The model card arrives in the next build step.')));
}

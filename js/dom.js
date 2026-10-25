// Tiny DOM helpers: build elements without innerHTML so data can never inject markup.
export const SVG_NS = 'http://www.w3.org/2000/svg';

function apply(el, attrs) {
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.setAttribute('class', v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  return el;
}
const append = (el, kids) => { el.append(...kids.flat(Infinity).filter(k => k != null && k !== false)); return el; };

export const h = (tag, attrs, ...kids) => append(apply(document.createElement(tag), attrs), kids);
export const s = (tag, attrs, ...kids) => append(apply(document.createElementNS(SVG_NS, tag), attrs), kids);

export const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
export const num = (x, d = 1) => (x == null ? '–' : Number(x).toFixed(d));
export const clear = el => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

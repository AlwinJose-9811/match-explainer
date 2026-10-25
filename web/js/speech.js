// "Listen" button: reads the commentary aloud with the browser's built-in speech synthesis.
// To sound natural it picks the best English voice installed (neural "Natural"/"Online" voices rank first, e.g. in
// Microsoft Edge), reads one sentence at a time with a livelier tone for "!" and a slower, building tone before "...",
// and leaves a human-sized pause between sentences. Nothing is sent anywhere by this site; whether a voice is processed
// online is up to the browser's own voice. A voice picker lets you choose another one.
import { h, clear } from './dom.js';

export const speechSupported = () => 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
let chosen = null;          // voiceURI picked by the user (kept for this page visit only)
let token = 0;              // increments to cancel an utterance chain

export function stopSpeaking() { token++; if (speechSupported()) window.speechSynthesis.cancel(); }

/** Higher is better. Non-English voices are excluded. */
export function voiceScore(v) {
  if (!/^en/i.test(v.lang)) return -1000;
  let s = 0;
  if (/natural|neural/i.test(v.name)) s += 100;
  if (/online/i.test(v.name)) s += 60;
  if (/google/i.test(v.name)) s += 40;
  if (/(aria|jenny|guy|ryan|sonia|libby|davis|michelle|mia|william|natasha|clara|eric|steffan|brian|emma)/i.test(v.name)) s += 30;
  if (/en[-_]GB/i.test(v.lang)) s += 20; else if (/en[-_]US/i.test(v.lang)) s += 15; else if (/en[-_]AU/i.test(v.lang)) s += 10;
  if (/(zira|david|mark|hazel)\b/i.test(v.name) && !/natural|online/i.test(v.name)) s -= 20;   // the older robotic Windows voices
  return s;
}
const englishVoices = () => window.speechSynthesis.getVoices().filter(v => voiceScore(v) > -1000).sort((a, b) => voiceScore(b) - voiceScore(a));
const currentVoice = () => { const vs = englishVoices(); return vs.find(v => v.voiceURI === chosen) || vs[0] || null; };

/** Split commentary into sentences: [{ text, kind }] where kind is 'excited' (!), 'build' (...) or 'plain'. */
export function sentences(text) {
  return text.replace(/\.\.\./g, '…').split(/(?<=[.!?…])\s+/).map(t => t.trim()).filter(Boolean)
    .map(t => ({ text: t.replace(/…$/, ','), kind: t.endsWith('!') ? 'excited' : t.endsWith('…') ? 'build' : 'plain' }));
}
const PROSODY = { excited: { rate: 1.06, pitch: 1.12, pause: 200 }, build: { rate: 0.9, pitch: 0.98, pause: 480 }, plain: { rate: 0.97, pitch: 1.0, pause: 300 } };

function speakAll(text, onDone) {
  const mine = ++token, list = sentences(text), voice = currentVoice();
  window.speechSynthesis.cancel();
  const next = i => {
    if (mine !== token) return;
    if (i >= list.length) { onDone(); return; }
    const p = PROSODY[list[i].kind], u = new SpeechSynthesisUtterance(list[i].text);
    if (voice) { u.voice = voice; u.lang = voice.lang; } else u.lang = 'en-GB';
    u.rate = p.rate; u.pitch = p.pitch; u.volume = 1;
    u.onend = () => setTimeout(() => next(i + 1), p.pause);
    u.onerror = () => { if (mine === token) onDone(); };
    window.speechSynthesis.speak(u);
  };
  next(0);
}

/** A "Listen" button plus a voice picker. Returns null when the browser has no speech synthesis. */
export function listenButton(getText, label = 'Listen') {
  if (!speechSupported()) return null;
  const btn = h('button', { type: 'button', class: 'btn', 'aria-pressed': 'false' }, `\u{1F50A} ${label}`);
  const select = h('select', { class: 'voice-pick', 'aria-label': 'Choose the voice' });
  const reset = () => { btn.setAttribute('aria-pressed', 'false'); btn.textContent = `\u{1F50A} ${label}`; };
  const fill = () => {
    const vs = englishVoices();
    clear(select).append(...vs.map(v => h('option', { value: v.voiceURI, selected: v === currentVoice() }, `${v.name.replace(/^Microsoft /, '')}${/natural|neural|online/i.test(v.name) ? ' ★' : ''}`)));
    select.hidden = vs.length < 2;
  };
  fill();
  window.speechSynthesis.addEventListener('voiceschanged', fill);   // voices load asynchronously in most browsers
  select.addEventListener('change', () => { chosen = select.value; if (btn.getAttribute('aria-pressed') === 'true') { stopSpeaking(); reset(); } });
  btn.addEventListener('click', () => {
    if (btn.getAttribute('aria-pressed') === 'true') { stopSpeaking(); reset(); return; }
    btn.setAttribute('aria-pressed', 'true');
    btn.textContent = '⏹ Stop';
    speakAll(getText(), reset);
  });
  return h('span', { class: 'listen' }, btn, select,
    h('span', { class: 'muted voice-hint' }, '★ = most natural voices. For the best voice use Microsoft Edge.'));
}

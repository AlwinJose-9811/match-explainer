// "Listen" button. Preferred: a recorded neural commentary voice (audio files made at build time, plays offline on any
// device). Fallback, or if you pick another voice: the browser's own speech synthesis. For that we choose the best
// English voice installed (neural "Natural"/"Online" voices rank first, e.g. in Microsoft Edge), read one sentence at a
// time with a livelier tone for "!" and a slower, building tone before "...", and leave human-sized pauses.
// Nothing is sent anywhere by this site; whether a browser voice is processed online is up to the browser.
import { h, clear } from './dom.js';

const RECORDED = '__recorded';
export const speechSupported = () => 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
let chosen = null;          // voiceURI picked by the user (kept for this page visit only)
let token = 0;              // increments to cancel an utterance chain
let currentAudio = null;

export function stopSpeaking() {
  token++;
  if (currentAudio) { currentAudio.pause(); currentAudio.currentTime = 0; currentAudio = null; }
  if (speechSupported()) window.speechSynthesis.cancel();
}

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
const englishVoices = () => (speechSupported() ? window.speechSynthesis.getVoices() : []).filter(v => voiceScore(v) > -1000).sort((a, b) => voiceScore(b) - voiceScore(a));
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

function playRecording(url, onDone, onFail) {
  stopSpeaking();
  const a = new Audio(url);
  currentAudio = a;
  a.onended = () => { if (currentAudio === a) currentAudio = null; onDone(); };
  a.onerror = () => { if (currentAudio === a) currentAudio = null; onFail(); };
  a.play().catch(() => { if (currentAudio === a) currentAudio = null; onFail(); });
}

/** A "Listen" button plus a voice picker. `audioUrl` is the recorded clip (optional). Null when nothing can speak. */
export function listenButton(getText, label = 'Listen', audioUrl = null) {
  if (!audioUrl && !speechSupported()) return null;
  const btn = h('button', { type: 'button', class: 'btn', 'aria-pressed': 'false' }, `\u{1F50A} ${label}`);
  const select = h('select', { class: 'voice-pick', 'aria-label': 'Choose the voice' });
  const hint = h('span', { class: 'muted voice-hint' });
  let useRecording = !!audioUrl;
  const reset = () => { btn.setAttribute('aria-pressed', 'false'); btn.textContent = `\u{1F50A} ${label}`; };
  const fill = () => {
    const vs = englishVoices(), cur = currentVoice();
    clear(select).append(...(audioUrl ? [h('option', { value: RECORDED, selected: useRecording }, 'Commentator (recorded)')] : []),
      ...vs.map(v => h('option', { value: v.voiceURI, selected: !useRecording && v === cur }, `${v.name.replace(/^Microsoft /, '')}${/natural|neural|online/i.test(v.name) ? ' ★' : ''}`)));
    select.hidden = select.options.length < 2;
    hint.textContent = useRecording ? 'Recorded British commentator voice (works offline).'
      : '★ = most natural browser voices. In Microsoft Edge these sound best.';
  };
  fill();
  if (speechSupported()) window.speechSynthesis.addEventListener('voiceschanged', fill);   // voices load asynchronously in most browsers
  select.addEventListener('change', () => {
    useRecording = select.value === RECORDED;
    if (!useRecording) chosen = select.value;
    stopSpeaking(); reset(); fill();
  });
  const speakWithBrowser = () => (speechSupported() ? speakAll(getText(), reset) : reset());
  btn.addEventListener('click', () => {
    if (btn.getAttribute('aria-pressed') === 'true') { stopSpeaking(); reset(); return; }
    btn.setAttribute('aria-pressed', 'true');
    btn.textContent = '⏹ Stop';
    if (useRecording) playRecording(audioUrl, reset, () => { useRecording = false; fill(); speakWithBrowser(); });   // a missing clip falls back to the browser voice
    else speakWithBrowser();
  });
  return h('span', { class: 'listen' }, btn, select, hint);
}

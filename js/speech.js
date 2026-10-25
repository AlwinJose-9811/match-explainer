// "Listen" button: reads text aloud with the browser's built-in speech synthesis (no network, no API key).
import { h } from './dom.js';

export const speechSupported = () => 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

export function stopSpeaking() { if (speechSupported()) window.speechSynthesis.cancel(); }

function pickVoice() {
  const voices = window.speechSynthesis.getVoices();
  return voices.find(v => /^en[-_]GB/i.test(v.lang)) || voices.find(v => /^en/i.test(v.lang)) || null;
}

/** Returns a toggle button that speaks getText(), or null when the browser has no speech synthesis. */
export function listenButton(getText, label = 'Listen') {
  if (!speechSupported()) return null;
  const btn = h('button', { type: 'button', class: 'btn', 'aria-pressed': 'false' }, `\u{1F50A} ${label}`);
  const reset = () => { btn.setAttribute('aria-pressed', 'false'); btn.textContent = `\u{1F50A} ${label}`; };
  btn.addEventListener('click', () => {
    if (btn.getAttribute('aria-pressed') === 'true') { stopSpeaking(); reset(); return; }
    stopSpeaking();
    const u = new SpeechSynthesisUtterance(getText());
    const v = pickVoice();
    if (v) { u.voice = v; u.lang = v.lang; } else u.lang = 'en-GB';
    u.rate = 0.95;
    u.onend = u.onerror = reset;
    btn.setAttribute('aria-pressed', 'true');
    btn.textContent = '⏹ Stop';
    window.speechSynthesis.speak(u);
  });
  return btn;
}

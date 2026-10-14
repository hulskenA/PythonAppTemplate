// Helpers every page uses: elements, escaping, dates, the API, a toast.
export const $ = (id) => document.getElementById(id);

/** Text made safe to put in HTML. Use it on anything that came from a person or the server. */
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/** "14:05" today, "3 Oct 14:05" otherwise. */
export function when(ts) {
  const d = new Date(ts);
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} ${time}`;
}

/**
 * Calls the app's API. Always resolves to an object with ok and message, so pages can show
 * the message as it is. Changes carry X-Requested-By, which the server requires.
 */
export async function api(method, url, body) {
  const opts = { method, headers: { Accept: 'application/json' }, cache: 'no-store' };
  if (method !== 'GET') opts.headers['X-Requested-By'] = 'app';
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  try {
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => null);
    if (!data) return { ok: false, message: res.status >= 500 ? 'The app could not answer for a moment. Try again.' : `The app answered ${res.status}.` };
    return { ok: res.ok && data.ok !== false, ...data };
  } catch {
    return { ok: false, message: 'The app cannot be reached. Check your connection.' };
  }
}

let toastTimer = null;
/** A short message at the bottom of the page. kind: 'info' or 'error'. */
export function toast(message, kind = 'info') {
  const t = $('toast');
  if (!t) return;
  t.textContent = message;
  t.dataset.kind = kind;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, kind === 'error' ? 8000 : 4000);
}

/** Who is signed in; fills the header (name, sign-out link) and the app's name. */
export async function loadMe() {
  const r = await api('GET', '/api/me');
  if (!r.ok) return null;
  document.querySelectorAll('[data-app-name]').forEach((el) => { el.textContent = r.app; });
  document.title = r.app;
  if (r.me) {
    $('who-name').textContent = r.me.name;
    $('who').hidden = false;
    if (r.signOut) { $('sign-out').href = r.signOut; $('sign-out').hidden = false; }
  }
  return r;
}

// The home page: who you are, and the example message board.
import { $, esc, when, api, toast, loadMe } from './common.js';

let me = null;

function renderFacts(r) {
  const rows = r.me
    ? [['Account', r.me.user], ['Name', r.me.name], ['Email', r.me.email || '—'], ['Groups', r.me.groups.join(', ') || 'none']]
    : [['Sign-in', r.signin === 'none' ? 'none: a public app' : 'nobody signed in']];
  $('facts').innerHTML = rows.map(([k, v]) => `<dt class="ah-label">${esc(k)}</dt><dd class="data">${esc(v)}</dd>`).join('');
  if (r.me) $('hello-label').textContent = `Hello ${r.me.name.split(' ')[0]}`;
}

async function loadMessages() {
  const r = await api('GET', '/api/messages');
  if (!r.ok) { $('messages').innerHTML = `<li class="small soft">${esc(r.message)}</li>`; return; }
  const admin = me?.groups.includes('admins');
  $('messages').innerHTML = r.messages.map((m) => `<li>
      <span class="msg-text">${esc(m.text)}</span>
      <span class="msg-meta"><span class="data soft">${esc(m.by)} · ${esc(when(m.at))}</span>${admin ? `<button type="button" class="link-btn" data-delete="${m.id}">Delete</button>` : ''}</span>
    </li>`).join('') || '<li class="small soft">No message yet. Be the first.</li>';
}

$('post-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const err = $('post-error'); err.hidden = true;
  const btn = $('post-btn'); btn.disabled = true;
  const r = await api('POST', '/api/messages', { text: $('post-text').value });
  btn.disabled = false;
  if (!r.ok) { err.textContent = r.message; err.hidden = false; return; }
  $('post-text').value = '';
  toast(r.message);
  loadMessages();
});

$('messages').addEventListener('click', async (e) => {
  const b = e.target.closest('button[data-delete]');
  if (!b) return;
  b.disabled = true;
  const r = await api('DELETE', `/api/messages/${b.dataset.delete}`);
  toast(r.message, r.ok ? 'info' : 'error');
  loadMessages();
});

const r = await loadMe();
if (r) {
  me = r.me;
  renderFacts(r);
  const open = r.signin === 'none';
  if (!r.me && !open) $('post-form').hidden = true;
  $('post-note').textContent = open ? 'This app is public: you post as Anonymous, and anyone can read it.'
    : me?.groups.includes('admins') ? 'As an admin, you can also delete messages.' : '';
  if (open) $('facts-note').textContent = 'This app is public: there is no sign-in in front of it, so anyone with its address can open it.';
}
loadMessages();
setInterval(() => { if (!document.hidden) loadMessages(); }, 15_000);

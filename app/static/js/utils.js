export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export const state = {
  recallId: null,
  recallStage: null,
  memoryId: null,
  latestCardId: null,
  cards: [],
  placeTags: [],
  recallQuestions: [],
  hintLevel: 0,
  hasHintAnswer: false,
};

export function getUserId() {
  return $('#userId')?.value.trim() || 'demo-user';
}

export function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
}

export function formatDate(value, withTime = false) {
  if (!value) return '';
  const date = new Date(value);
  return new Intl.DateTimeFormat('ko-KR', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'long' }).format(date);
}

export function toast(message, tone = 'normal') {
  const el = $('#toast');
  el.textContent = message;
  el.dataset.tone = tone;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 3200);
}

export function setLoading(active, message = '기억을 천천히 정리하고 있어요') {
  const loading = $('#loading');
  $('b', loading).textContent = message;
  loading.classList.toggle('hidden', !active);
}

export function setLoadingSequence(messages, interval = 2200) {
  let index = 0;
  setLoading(true, messages[index]);
  const timer = window.setInterval(() => {
    index = Math.min(index + 1, messages.length - 1);
    setLoading(true, messages[index]);
  }, interval);
  return () => {
    window.clearInterval(timer);
    setLoading(false);
  };
}

export function switchTab(name) {
  $$('.tabs button').forEach((button) => button.classList.toggle('active', button.dataset.tab === name));
  $$('.panel').forEach((panel) => panel.classList.toggle('active', panel.id === name));
  history.replaceState(null, '', `#${name}`);
  window.scrollTo({ top: document.querySelector('.tabs').offsetTop - 90, behavior: 'smooth' });
  document.dispatchEvent(new CustomEvent('tabchange', { detail: name }));
}

export function emptyState(icon, title, text) {
  return `<div class="empty-state"><span>${icon}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p></div>`;
}

export function placeOptions(selected = '', includeEmpty = true) {
  const empty = includeEmpty ? '<option value="">장소를 선택하지 않을게요</option>' : '';
  return empty + state.placeTags.map((tag) => `<option value="${escapeHtml(tag)}" ${tag === selected ? 'selected' : ''}>${escapeHtml(tag)}</option>`).join('');
}

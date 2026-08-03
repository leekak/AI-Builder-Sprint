import { get } from './api.js';
import { clearRegisterResult, initRegister, loadMemoriesCount, loadRecentMemories, renderRegisterPlaces } from './register.js';
import { closeRecallWorkspace, initRecall, loadDue } from './recall.js';
import { initCards, loadCards } from './cards.js';
import { initTown, loadTownCards, renderTownPlaces, updateTownStatus } from './town.js';
import { loadTownMap } from './map.js';
import { initAdmin } from './admin.js';
import { initUserSession } from './userSession.js';
import { $, $$, emptyState, hasUserSession, state, switchTab, toast } from './utils.js';

function applyPrivateSessionState() {
  const loggedIn = hasUserSession();
  document.body.classList.toggle('user-logged-out', !loggedIn);
  ['register', 'recall', 'cards'].forEach((id) => {
    const panel = $(`#${id}`);
    panel.classList.toggle('login-required', !loggedIn);
    panel.setAttribute('aria-disabled', String(!loggedIn));
  });
  if (!loggedIn) {
    $('#memoryCount').textContent = '—';
    $('#cardCount').textContent = '—';
    $('#dueBadge').classList.add('hidden');
    $('#recentMemories').innerHTML = emptyState('⌁', '로그인 후 기억을 맡길 수 있어요', '상단에 사용자 아이디를 입력하고 로그인해 주세요.');
    $('#dueList').innerHTML = emptyState('⌁', '로그인 후 회상을 시작할 수 있어요', '상단에 사용자 아이디를 입력하고 로그인해 주세요.');
    $('#myCards').innerHTML = emptyState('⌁', '로그인 후 내 추억 카드를 볼 수 있어요', '상단에 사용자 아이디를 입력하고 로그인해 주세요.');
    closeRecallWorkspace();
  }
}

async function reloadPrivateData() {
  applyPrivateSessionState();
  if (!hasUserSession()) return;
  await Promise.all([loadMemoriesCount(), loadRecentMemories(), loadDue(), loadCards()]);
}

async function loadPlaceTags() {
  const data = await get('/place-tags');
  state.placeTags = data.place_tags || [];
  renderRegisterPlaces(); renderTownPlaces();
}

async function initialize() {
  $('#memoryForm').memory_date.value = new Date().toISOString().slice(0, 10);
  initRegister(); initRecall(); initCards(); initTown(); initAdmin(); initUserSession();
  $$('.tabs button').forEach((button) => button.addEventListener('click', () => switchTab(button.dataset.tab)));
  document.addEventListener('tabchange', (event) => {
    if (event.detail !== 'register') clearRegisterResult();
    if (event.detail !== 'recall') closeRecallWorkspace();
    if (event.detail === 'recall') loadDue();
    if (event.detail === 'cards') loadCards();
    if (event.detail === 'town') Promise.all([loadTownCards(), updateTownStatus(), loadTownMap()]);
  });
  document.addEventListener('memorycreated', loadDue);
  document.addEventListener('memorycreated', loadRecentMemories);
  document.addEventListener('memorydeleted', () => Promise.all([loadDue(), loadCards(), loadTownCards(), updateTownStatus(), loadTownMap()]));
  document.addEventListener('cardcreated', () => Promise.all([loadCards(), loadDue()]));
  document.addEventListener('townchanged', () => Promise.all([updateTownStatus(), loadTownMap()]));
  document.addEventListener('adminchange', () => Promise.all([loadTownCards(), updateTownStatus()]));
  document.addEventListener('userchange', reloadPrivateData);
  applyPrivateSessionState();
  try {
    await loadPlaceTags();
    await Promise.all([loadTownCards(), updateTownStatus()]);
    await reloadPrivateData();
  } catch (error) { toast(`초기 정보를 불러오지 못했습니다. ${error.message}`, 'error'); }
  const initial = location.hash.slice(1);
  if (['register', 'recall', 'cards', 'town'].includes(initial)) switchTab(initial);
}

initialize();

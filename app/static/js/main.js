import { get } from './api.js';
import { clearRegisterResult, initRegister, loadMemoriesCount, loadRecentMemories, renderRegisterPlaces } from './register.js';
import { closeRecallWorkspace, initRecall, loadDue } from './recall.js';
import { initCards, loadCards } from './cards.js';
import { initTown, loadTownCards, renderTownPlaces, updateTownStatus } from './town.js';
import { loadTownMap } from './map.js';
import { initAdmin } from './admin.js';
import { initUserSession } from './userSession.js';
import { $, $$, state, switchTab, toast } from './utils.js';

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
  const reloadForUser = () => Promise.all([loadMemoriesCount(), loadRecentMemories(), loadDue(), loadCards()]);
  $('#userId').addEventListener('change', reloadForUser);
  document.addEventListener('userchange', reloadForUser);
  try {
    await loadPlaceTags();
    await Promise.all([loadMemoriesCount(), loadRecentMemories(), loadDue(), loadCards(), loadTownCards(), updateTownStatus()]);
  } catch (error) { toast(`초기 정보를 불러오지 못했습니다. ${error.message}`, 'error'); }
  const initial = location.hash.slice(1);
  if (['register', 'recall', 'cards', 'town'].includes(initial)) switchTab(initial);
}

initialize();

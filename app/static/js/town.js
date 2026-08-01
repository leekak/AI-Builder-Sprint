import { adminDelete, adminGet, adminPost, get, isAdmin } from './api.js';
import { $, emptyState, escapeHtml, formatDate, state, toast } from './utils.js';
import { loadTownMap } from './map.js';

async function loadPlaceContributions(place) {
  const box = $('#townContributions');
  if (!isAdmin()) { box.classList.add('hidden'); box.innerHTML = ''; return; }
  box.classList.remove('hidden');
  box.innerHTML = emptyState('◌', '기여 조각을 불러오는 중이에요', '잠시만 기다려 주세요.');
  try {
    const items = await adminGet(`/archive/places/${encodeURIComponent(place)}/contributions`);
    if (!items.length) {
      box.innerHTML = emptyState('◌', '아직 모인 회상 조각이 없어요', '누군가 이 장소로 공유하면 여기에 익명으로 표시됩니다.');
      return;
    }
    box.innerHTML = `<h3 class="contributions-heading">관리자용 · 모인 회상 조각 ${items.length}개 (작성자 비공개)</h3>` + items.map((item, index) => `<article class="contribution-fragment"><div class="meta">조각 ${index + 1} · ${formatDate(item.created_at, true)}</div><p><b>원본 공개 전</b> ${escapeHtml(item.pre_reveal_text || '(없음)')}</p>${item.post_reveal_text ? `<p><b>원본 공개 후</b> ${escapeHtml(item.post_reveal_text)}</p>` : ''}</article>`).join('');
  } catch (error) {
    box.innerHTML = emptyState('!', '기여 조각을 불러오지 못했어요', error.message);
  }
}

export async function updateTownStatus() {
  const place = $('#townPlace').value;
  if (!place || !state.placeTags.includes(place)) {
    $('#townStatus').textContent = place ? '목록에서 표준 지역을 선택해 주세요.' : '살펴볼 지역을 검색해 주세요.';
    $('#generateTown').disabled = true;
    $('#townContributions').classList.add('hidden');
    return;
  }
  const box = $('#townStatus');
  box.textContent = '기여 상태를 확인하는 중…';
  try {
    const status = await get(`/archive/places/${encodeURIComponent(place)}/status`);
    const progress = status.latest_card_id ? status.new_contributors : status.distinct_contributors;
    const ratio = Math.min(100, (progress / status.minimum_required) * 100);
    const remaining = Math.max(0, status.minimum_required - progress);
    const message = status.privacy_review_required
      ? '기존 카드 개인정보 보호 재처리 필요'
      : status.can_generate
        ? (status.latest_card_id ? '기존 카드 갱신 가능' : '첫 카드 생성 가능')
        : status.latest_card_id
          ? `새 참여자 ${remaining}명 더 필요`
          : `${remaining}명 더 필요`;
    const label = status.latest_card_id ? '새 참여자' : '전체 참여자';
    box.innerHTML = `<b>${label} ${progress}/${status.minimum_required}명</b><span class="meter"><i style="width:${ratio}%"></i></span><span>${message}</span>`;
    $('#generateTown').textContent = status.privacy_review_required ? '개인정보 보호 재처리' : (status.latest_card_id ? '동네 카드 갱신하기' : '동네 카드 만들기');
    $('#generateTown').disabled = !status.can_generate;
  } catch (error) { box.textContent = error.message; $('#generateTown').disabled = true; }
  await loadPlaceContributions(place);
}

export async function loadTownCards() {
  const container = $('#townCards');
  container.innerHTML = emptyState('⌂', '동네 카드를 불러오는 중이에요', '잠시만 기다려 주세요.');
  try {
    const cards = await get('/archive/places');
    if (!cards.length) return container.innerHTML = emptyState('⌂', '아직 완성된 동네 카드가 없어요', '같은 장소를 기억하는 사람들이 모이면 공동체의 이야기가 시작됩니다.');
    container.innerHTML = cards.map((card) => `<article class="town-card"><div class="meta">${escapeHtml(card.place)} · ${card.contributors}명의 기억 · v${card.version} · ${formatDate(card.updated_at)}</div><h3>${escapeHtml(card.card_title)}</h3><p>${escapeHtml(card.story)}</p><p><b>${escapeHtml(card.reflection)}</b></p>${isAdmin() ? `<div class="card-actions"><button type="button" class="danger-outline delete-town-card" data-card-id="${card.id}" data-place="${escapeHtml(card.place)}">동네 카드 삭제</button></div>` : ''}</article>`).join('');
    container.querySelectorAll('.delete-town-card').forEach((button) => button.addEventListener('click', () => deleteTownCard(button.dataset.cardId, button.dataset.place)));
  } catch (error) { container.innerHTML = emptyState('!', '동네 카드를 불러오지 못했어요', error.message); }
}

async function generateTownCard() {
  const place = $('#townPlace').value;
  if (!state.placeTags.includes(place)) return toast('목록에서 표준 지역을 선택해 주세요.', 'error');
  try {
    const card = await adminPost(`/archive/places/${encodeURIComponent(place)}/card`);
    toast(`‘${card.card_title}’ 동네 카드 v${card.version}이 ${card.version > 1 ? '갱신' : '완성'}되었습니다.`);
    await Promise.all([loadTownCards(), updateTownStatus(), loadTownMap()]);
  } catch (error) { toast(error.message, 'error'); }
}

async function deleteTownCard(cardId, place) {
  if (!window.confirm(`‘${place}’ 동네 추억 카드를 삭제할까요?\n\n공유된 비식별 기억 조각은 유지되어 추후 관리자가 카드를 다시 만들 수 있습니다.`)) return;
  try {
    const result = await adminDelete(`/archive/places/cards/${encodeURIComponent(cardId)}`);
    toast(result.message);
    await Promise.all([loadTownCards(), updateTownStatus(), loadTownMap()]);
    document.dispatchEvent(new CustomEvent('townchanged'));
  } catch (error) {
    if (error.status === 401 || error.status === 403) document.dispatchEvent(new CustomEvent('adminchange'));
    toast(error.message, 'error');
  }
}

export function renderTownPlaces() {
  // Do not imply that the first configured place was chosen by the user.
  // A place is selected only through search/autocomplete or a map marker.
  $('#townPlace').value = '';
}

export function initTown() {
  $('#refreshTown').addEventListener('click', () => Promise.all([loadTownCards(), updateTownStatus(), loadTownMap()]));
  $('#townPlace').addEventListener('change', updateTownStatus);
  $('#generateTown').addEventListener('click', generateTownCard);
}

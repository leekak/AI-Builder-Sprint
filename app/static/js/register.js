import { del, get, patch, postForm, api } from './api.js';
import { $, emptyState, escapeHtml, formatDate, getUserId, setLoading, setLoadingSequence, state, toast } from './utils.js';

export async function loadMemoriesCount() {
  const requestedUser = getUserId();
  if (!requestedUser) { $('#memoryCount').textContent = '—'; return; }
  try {
    const items = await get('/memories');
    if (requestedUser !== getUserId()) return;
    $('#memoryCount').textContent = items.length;
  } catch {
    if (requestedUser === getUserId()) $('#memoryCount').textContent = '—';
  }
}

export async function loadRecentMemories() {
  const container = $('#recentMemories');
  if (!container) return;
  const requestedUser = getUserId();
  if (!requestedUser) {
    container.innerHTML = emptyState('⌁', '로그인 후 기억을 맡길 수 있어요', '상단에 사용자 아이디를 입력하고 로그인해 주세요.');
    return;
  }
  container.innerHTML = emptyState('◌', '기억을 불러오는 중이에요', '잠시만 기다려 주세요.');
  try {
    const items = await get('/memories');
    if (requestedUser !== getUserId()) return;
    if (!items.length) return container.innerHTML = emptyState('◌', '아직 맡긴 기억이 없어요', '첫 장면을 기록하면 이곳에서 관리할 수 있어요.');
    container.innerHTML = items.map((item) => {
      const title = item.analysis?.title || item.comment.slice(0, 32) || '이름을 붙이지 않은 기억';
      const next = item.recall_schedule?.next_recall_at;
      const status = item.recall_schedule?.completed ? '회상 완료' : (next ? `${formatDate(next, true)} 회상 예정` : '회상 일정 대기 중');
      const place = item.place_label || item.place_tag;
      const recommendation = !item.place_tag && item.suggested_place_tag ? ` · AI 추천 ${escapeHtml(item.suggested_place_tag)} 확인 필요` : '';
      return `<article class="memory-record"><div><div class="meta">${formatDate(item.memory_date)}${place ? ` · ${escapeHtml(place)}` : ''}${recommendation}</div><h4>${escapeHtml(title)}</h4><p>${escapeHtml(status)}</p></div><button type="button" class="danger-outline delete-memory" data-memory-id="${item.id}">기억 삭제</button></article>`;
    }).join('');
    container.querySelectorAll('.delete-memory').forEach((button) => button.addEventListener('click', () => deleteMemory(button.dataset.memoryId)));
  } catch (error) {
    if (requestedUser === getUserId()) container.innerHTML = emptyState('!', '기억 목록을 불러오지 못했어요', error.message);
  }
}

export async function deleteMemory(memoryId) {
  if (!window.confirm('이 기억을 완전히 삭제할까요?\n\n원본 사진·코멘트·회상·내 추억 카드는 복구할 수 없습니다. 이미 발행된 동네 카드의 비식별 조각은 작성자 연결 없이 유지됩니다.')) return false;
  setLoading(true, '개인 기억과 연결 정보를 안전하게 삭제하고 있어요');
  try {
    const result = await del(`/memories/${memoryId}`);
    toast(result.message);
    await Promise.all([loadMemoriesCount(), loadRecentMemories()]);
    document.dispatchEvent(new CustomEvent('memorydeleted', { detail: result }));
    return true;
  } catch (error) {
    toast(`삭제하지 못했어요. ${error.message}`, 'error');
    return false;
  } finally { setLoading(false); }
}

export function renderRegisterPlaces() {
  $('#placeTagsList').innerHTML = state.placeTags.map((tag) => `<option value="${escapeHtml(tag)}"></option>`).join('');
  $('#recallPlace').value = '';
}

export function clearRegisterResult() {
  const result = $('#registerResult');
  if (!result) return;
  // 실패 결과에는 재시도 동작이 있으므로 보존하고, 성공/진행 안내만 닫는다.
  if (result.dataset.memoryId && result.querySelector('.retry-analysis')) return;
  result.replaceChildren();
  result.className = 'status-box hidden';
  result.dataset.memoryId = '';
}

function placeConfirmationMarkup(item) {
  if (!item.place_label && !item.suggested_place_tag && !item.place_tag) return '';
  const selected = item.place_tag || item.suggested_place_tag || '';
  const heading = item.suggested_place_tag ? `AI가 ‘${escapeHtml(item.suggested_place_tag)}’ 지역으로 추천했어요.` : '입력한 장소와 연결되는 동네를 찾지 못했어요.';
  const guide = item.suggested_place_tag ? '추천 결과를 확인하거나 다른 지역으로 바꿀 수 있어요.' : '개인 기록은 그대로 저장됐어요. 동네 카드에 공유하려면 가까운 지역을 직접 선택해 주세요.';
  return `<div class="place-confirm"><div><b>${heading}</b><small>${guide}<br>개인 기록에는 ‘${escapeHtml(item.place_label || '입력한 장소 없음')}’ 그대로 남고, 확정한 태그만 동네 카드 묶기에 사용됩니다.</small></div><div><input class="confirm-place-select" list="placeTagsList" value="${escapeHtml(selected)}" placeholder="표준 지역 검색" aria-label="표준 지역 태그"><button type="button" class="secondary confirm-place" data-memory-id="${item.id}">지역 태그 확정</button></div></div>`;
}

async function confirmPlace(memoryId, container) {
  const placeTag = container.querySelector('.confirm-place-select').value || null;
  if (placeTag && !state.placeTags.includes(placeTag)) return toast('목록에서 표준 지역을 선택해 주세요.', 'error');
  try {
    const item = await patch(`/memories/${memoryId}/place-tag`, { place_tag: placeTag });
    container.innerHTML = `<b>${placeTag ? `${escapeHtml(placeTag)}로 확정했어요.` : '표준 지역 태그를 지정하지 않았어요.'}</b><small>구체적인 장소 기록은 그대로 보관됩니다.</small>`;
    toast(item.place_tag ? `${item.place_tag} 지역 태그를 확정했습니다.` : '지역 태그를 비워두었습니다.');
    await loadRecentMemories();
  } catch (error) { toast(error.message, 'error'); }
}

async function processMemory(memoryId) {
  const result = $('#registerResult');
  const finishLoading = setLoadingSequence(['사진 속 글자를 확인하고 있어요', '기억의 장소와 인물을 정리하고 있어요', '회상에 필요한 질문 단서를 만들고 있어요']);
  try {
    const userId = getUserId();
    if (!userId) throw new Error('먼저 사용자 로그인을 해주세요.');
    const processed = await api(`/memories/${memoryId}/process`, { method: 'POST', headers: { 'X-User-Id': userId } });
    const item = processed.memory;
    const title = item.analysis?.title || '이름을 붙이지 않은 기억';
    result.className = 'status-box';
    result.innerHTML = `<b>${escapeHtml(title)}</b><br><span>${formatDate(item.recall_schedule.first_recall_at, true)}에 첫 회상을 만나요.</span>${placeConfirmationMarkup(item)}`;
    result.dataset.memoryId = '';
    toast('기억의 맥락 정리를 완료했습니다.');
    document.dispatchEvent(new CustomEvent('memorycreated'));
    return true;
  } catch (error) {
    result.className = 'status-box warning';
    result.dataset.memoryId = memoryId;
    result.innerHTML = `<b>기억은 안전하게 저장됐어요.</b><br><span>AI 맥락 정리는 완료하지 못했습니다. ${escapeHtml(error.message)}</span><br><button type="button" class="secondary retry-analysis">분석 다시 시도</button>`;
    toast('기억은 저장됐지만 AI 분석을 다시 시도해야 합니다.', 'error');
    return false;
  } finally { finishLoading(); }
}

async function submitMemory(event) {
  event.preventDefault();
  if (!getUserId()) return toast('상단에서 사용자 아이디로 먼저 로그인해 주세요.', 'error');
  const form = event.currentTarget;
  const file = form.image.files?.[0];
  if (form.use_ocr.checked && !file) return toast('사진 속 글자를 활용하려면 사진을 먼저 선택해 주세요.', 'error');
  if (form.memory_date.value > new Date().toISOString().slice(0, 10)) {
    return toast('기억 날짜는 오늘 이후로 설정할 수 없어요.', 'error');
  }

  const data = new FormData();
  ['comment', 'memory_date', 'first_recall_days', 'second_recall_days', 'place_label'].forEach((name) => {
    const value = form.elements[name]?.value;
    if (value !== undefined && value !== '') data.append(name, value);
  });
  data.append('use_ocr', form.use_ocr.checked ? 'true' : 'false');
  if (file) data.append('image', file);

  const result = $('#registerResult');
  // 이전 요청의 재시도용 ID가 새 등록 성공 안내에 남지 않도록 먼저 비운다.
  result.dataset.memoryId = '';
  result.className = 'status-box';
  result.textContent = '기억을 안전하게 맡기는 중입니다…';
  let memory = null;
  setLoading(true, '기억을 안전하게 저장하고 있어요');
  try {
    memory = await postForm('/memories', data);
    form.reset();
    form.memory_date.value = new Date().toISOString().slice(0, 10);
    form.first_recall_days.value = '7'; form.second_recall_days.value = '30';
    $('#commentCount').textContent = '0'; $('#imagePreview').classList.add('hidden');
    $('#uploadCopy').classList.remove('hidden'); $('#uploadZone').classList.remove('has-image');
    $('#removeImage').classList.add('hidden'); $('#replaceHint').classList.add('hidden');
    await loadMemoriesCount();
    result.innerHTML = '<b>기억을 안전하게 저장했어요.</b><br><span>이제 AI가 회상을 위한 맥락을 정리합니다.</span>';
    await processMemory(memory.id);
  } catch (error) {
    result.className = 'status-box error';
    result.textContent = `저장하지 못했어요. ${error.message}`;
    toast(error.message, 'error');
  } finally { setLoading(false); }
}

export function initRegister() {
  const form = $('#memoryForm');
  const todayStr = new Date().toISOString().slice(0, 10);
  form.memory_date.max = todayStr;
  form.memory_date.addEventListener('change', () => {
    if (form.memory_date.value > todayStr) {
      form.memory_date.value = todayStr;
      toast('기억 날짜는 오늘 이후로 설정할 수 없어요.', 'error');
    }
  });
  form.addEventListener('submit', submitMemory);
  $('#refreshMemories')?.addEventListener('click', loadRecentMemories);
  $('#demoPreset')?.addEventListener('click', () => {
    form.comment.value = '비 오는 저녁 광안리 해수욕장 근처에서 친구와 식사하고 바닷가를 걸었다.';
    form.place_label.value = '광안리 해수욕장 앞 작은 식당';
    form.memory_date.value = new Date().toISOString().slice(0, 10);
    form.first_recall_days.value = '7';
    form.second_recall_days.value = '30';
    $('#commentCount').textContent = form.comment.value.length;
    toast('발표용 예시를 채웠어요. 사진은 원하는 데모 이미지를 선택해 주세요.');
  });
  $('#registerResult').addEventListener('click', (event) => {
    const confirmButton = event.target.closest('.confirm-place');
    if (confirmButton) {
      confirmPlace(confirmButton.dataset.memoryId, confirmButton.closest('.place-confirm'));
      return;
    }
    if (!event.target.closest('.retry-analysis')) return;
    const memoryId = $('#registerResult').dataset.memoryId;
    if (memoryId) processMemory(memoryId);
  });
  form.comment.addEventListener('input', () => { $('#commentCount').textContent = form.comment.value.length; });
  form.image.addEventListener('change', () => {
    const file = form.image.files?.[0];
    const preview = $('#imagePreview');
    if (!file) {
      preview.classList.add('hidden'); $('#uploadCopy').classList.remove('hidden'); $('#uploadZone').classList.remove('has-image');
      $('#removeImage').classList.add('hidden'); $('#replaceHint').classList.add('hidden');
      return;
    }
    preview.src = URL.createObjectURL(file); preview.classList.remove('hidden');
    $('#uploadCopy').classList.add('hidden'); $('#uploadZone').classList.add('has-image');
    $('#removeImage').classList.remove('hidden'); $('#replaceHint').classList.remove('hidden');
  });
  $('#removeImage').addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    form.image.value = '';
    form.image.dispatchEvent(new Event('change'));
    toast('사진을 삭제했어요. 다른 사진을 다시 선택할 수 있어요.');
  });
}

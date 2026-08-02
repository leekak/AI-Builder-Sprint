import { del, get, post, protectedImage } from './api.js';
import { $, emptyState, escapeHtml, formatDate, setLoading, state, toast } from './utils.js';
import { deleteMemory } from './register.js';
import { previewAndShare } from './privacy.js';

async function imageMarkup(card) {
  const usesOriginal = Boolean(card.image_url);
  const url = usesOriginal ? card.image_url : card.generated_image_url;
  if (!url) return '';
  try {
    const label = !usesOriginal ? '<span class="ai-image-label">AI로 만든 추억 이미지</span>' : '';
    return `<div class="card-visual">${label}<img class="card-image" src="${await protectedImage(url)}" alt="${usesOriginal ? '원본 기억 사진' : 'AI로 만든 추억 이미지'}" /></div>`;
  }
  catch { return '<div class="status-box error">사진을 불러오지 못했어요.</div>'; }
}

function imageTools(card) {
  if (card.image_url) return '';
  const action = card.generated_image_url ? '추억 이미지 다시 만들기' : '추억 이미지 만들기';
  const status = card.image_generation_status === 'failed' ? '<small class="image-error">이전 이미지 생성에 실패했어요. 다시 시도할 수 있습니다.</small>' : '';
  return `<div class="image-tools"><div><b>추억을 이미지로 남겨보세요</b>${status}</div><button type="button" class="secondary generate-card-image" data-card-id="${card.id}">${action}</button>${card.generated_image_url ? `<button type="button" class="ghost delete-card-image" data-card-id="${card.id}">생성 이미지 삭제</button>` : ''}</div>`;
}

export async function loadCards() {
  const container = $('#myCards');
  container.innerHTML = emptyState('◇', '추억 카드를 불러오는 중이에요', '잠시만 기다려 주세요.');
  try {
    const showingArchived = $('#cardView').value === 'archived';
    state.cards = await get(`/cards?sort=${encodeURIComponent($('#cardSort').value)}&archived=${showingArchived}`);
    if (!showingArchived) $('#cardCount').textContent = state.cards.length;
    if (!state.cards.length) return container.innerHTML = showingArchived
      ? emptyState('◇', '숨겨둔 카드가 없어요', '보관 중인 카드는 그대로 유지되고 언제든 다시 볼 수 있어요.')
      : emptyState('◇', '완성된 카드가 아직 없어요', '첫 회상을 마치면 이곳에 추억이 차곡차곡 쌓입니다.');
    const articles = await Promise.all(state.cards.map(async (card) => {
      const history = (card.recall_history || []).map((item) => `<li><b>${item.stage}차 회상</b><small>${formatDate(item.completed_at, true)}</small>${item.initial_answer ? `<p>${escapeHtml(item.initial_answer)}</p>` : ''}${item.newly_recalled_text ? `<blockquote>원본을 본 뒤 · ${escapeHtml(item.newly_recalled_text)}</blockquote>` : ''}</li>`).join('');
      const shareLabel = card.town_share_status === 'published' ? '동네 카드에 반영됨' : (card.town_share_status === 'pending' ? '비식별 조각 공유됨 · 카드 생성 대기' : '');
      const latestStage = card.recall_history?.at(-1)?.stage || 1;
      const addedCopy = card.latest_recall_added_count > 0 ? `${card.latest_recall_added_count}개의 새로운 기억 조각이` : '새로운 회상 내용이';
      const updateNotice = latestStage > 1 ? `<div class="card-update">2차 회상에서 ${addedCopy} 기존 카드에 반영됐어요.</div>` : '';
      const shareControls = card.shared_to_town
        ? `<span class="place-fixed">공유된 동네 · <b>${escapeHtml(card.place_tag || '')}</b></span><button class="ghost unshare-town" data-card-id="${card.id}">공유 취소</button>`
        : `<input id="place-${card.id}" list="placeTagsList" value="${escapeHtml(card.place_tag || '')}" placeholder="공유 지역 검색" aria-label="공유 장소" autocomplete="off"><button class="secondary share-town" data-card-id="${card.id}">동네에 익명 공유</button>`;
      return `<article class="memory-card"><div class="meta">${formatDate(card.memory_date)}${card.place_label ? ` · ${escapeHtml(card.place_label)}` : ''} ${shareLabel ? `<span class="shared-chip ${card.town_share_status}">${escapeHtml(shareLabel)}</span>` : ''}</div><h3>${escapeHtml(card.card_title)}</h3>${updateNotice}${await imageMarkup(card)}${imageTools(card)}<p>${escapeHtml(card.story)}</p><p><b>${escapeHtml(card.reflection)}</b></p>${history ? `<details class="recall-history"><summary>${card.recall_history.length}번의 회상 과정 보기</summary><ol>${history}</ol></details>` : ''}<div class="card-actions">${shareControls}<button class="ghost archive-card" data-card-id="${card.id}" data-archived="${!showingArchived}">${showingArchived ? '다시 보관함에 놓기' : '카드 숨기기'}</button><button class="danger-outline delete-card-memory" data-memory-id="${card.memory_id}">개인 기억 삭제</button></div><p class="action-help">${card.shared_to_town ? '동네를 바꾸려면 먼저 공유를 취소해주세요. 카드 숨기기는 복구할 수 있고, 개인 기억 삭제는 원본과 회상을 함께 지워 복구할 수 없습니다.' : '카드 숨기기는 복구할 수 있고, 개인 기억 삭제는 원본과 회상을 함께 지워 복구할 수 없습니다.'}</p></article>`;
    }));
    container.innerHTML = articles.join('');
    container.querySelectorAll('.share-town').forEach((button) => button.addEventListener('click', () => shareTown(button.dataset.cardId, true)));
    container.querySelectorAll('.unshare-town').forEach((button) => button.addEventListener('click', () => shareTown(button.dataset.cardId, false)));
    container.querySelectorAll('.archive-card').forEach((button) => button.addEventListener('click', () => archiveCard(button.dataset.cardId, button.dataset.archived === 'true')));
    container.querySelectorAll('.generate-card-image').forEach((button) => button.addEventListener('click', () => generateCardImage(button.dataset.cardId)));
    container.querySelectorAll('.delete-card-image').forEach((button) => button.addEventListener('click', () => deleteCardImage(button.dataset.cardId)));
    container.querySelectorAll('.delete-card-memory').forEach((button) => button.addEventListener('click', async () => {
      if (await deleteMemory(button.dataset.memoryId)) await loadCards();
    }));
  } catch (error) { container.innerHTML = emptyState('!', '카드를 불러오지 못했어요', error.message); }
}

async function generateCardImage(cardId) {
  if (!window.confirm('추억 내용을 바탕으로 이미지를 만들까요?')) return;
  setLoading(true, '추억의 분위기를 이미지로 표현하고 있어요');
  try {
    await post(`/cards/${cardId}/generate-image`, { mode: 'text_illustration' });
    toast('추억 이미지를 완성했습니다.');
    await loadCards();
  } catch (error) { toast(error.message, 'error'); }
  finally { setLoading(false); }
}

async function deleteCardImage(cardId) {
  if (!window.confirm('AI로 생성한 이미지를 삭제할까요? 원본 사진과 텍스트 추억 카드는 유지됩니다.')) return;
  try {
    await del(`/cards/${cardId}/generated-image`);
    toast('생성 이미지를 삭제했습니다.');
    await loadCards();
  } catch (error) { toast(error.message, 'error'); }
}

async function shareTown(cardId, consent) {
  const placeTag = consent ? $(`#place-${CSS.escape(cardId)}`).value : null;
  if (consent && !placeTag) return toast('공유할 장소를 선택해 주세요.', 'error');
  if (consent && !state.placeTags.includes(placeTag)) return toast('목록에서 표준 지역을 선택해 주세요.', 'error');
  try {
    if (consent) {
      if (!await previewAndShare(cardId, placeTag)) return;
    } else await post(`/cards/${cardId}/share-to-town`, { consent: false, place_tag: null });
    toast(consent ? `${placeTag}의 동네 기억에 비식별 조각을 보탰습니다.` : '공유를 취소했습니다. 이미 발행된 동네 카드의 익명 조각은 유지될 수 있어요.');
    await loadCards(); document.dispatchEvent(new CustomEvent('townchanged'));
  } catch (error) { toast(error.message, 'error'); }
}

async function archiveCard(cardId, archived) {
  try {
    await post(`/cards/${cardId}/archive`, { archived });
    toast(archived ? '카드를 숨겼습니다. 숨겨둔 카드에서 복구할 수 있어요.' : '카드를 다시 보관함에 놓았습니다.');
    await loadCards();
  } catch (error) { toast(error.message, 'error'); }
}

export function initCards() {
  $('#refreshCards').addEventListener('click', loadCards);
  $('#cardSort').addEventListener('change', loadCards);
  $('#cardView').addEventListener('change', loadCards);
}

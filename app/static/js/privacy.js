import { post } from './api.js';
import { $, setLoading, toast } from './utils.js';

function showPreview(preview) {
  const dialog = $('#privacyPreview');
  $('#previewPlace').textContent = `${preview.place_tag} 동네 아카이브`;
  $('#previewPre').textContent = preview.safe_pre_text || '공유할 내용 없음';
  $('#previewPost').textContent = preview.safe_post_text || '';
  $('#previewPostWrap').classList.toggle('hidden', !preview.safe_post_text);
  const conflictBox = $('#previewConflict');
  if (preview.conflicting_card_id) {
    conflictBox.textContent = `이미 '${preview.conflicting_card_title || '다른 기억'}'(으)로 이 동네에 등록되어 있어요. 계속 진행하면 그 기억 대신 지금 이 기억으로 교체됩니다.`;
    conflictBox.classList.remove('hidden');
  } else {
    conflictBox.classList.add('hidden');
  }
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true });
  });
}

export async function previewAndShare(cardId, placeTag) {
  if (!placeTag) {
    toast('공유할 장소를 선택해 주세요.', 'error');
    return false;
  }
  setLoading(true, '공유할 내용을 안전하게 비식별화하고 있어요');
  let preview;
  try { preview = await post(`/cards/${cardId}/share-preview`, { place_tag: placeTag }); }
  finally { setLoading(false); }
  if (!await showPreview(preview)) return false;
  await post(`/cards/${cardId}/share-to-town`, {
    consent: true,
    place_tag: placeTag,
    preview_token: preview.preview_token,
    replace_existing: Boolean(preview.conflicting_card_id),
  });
  return true;
}

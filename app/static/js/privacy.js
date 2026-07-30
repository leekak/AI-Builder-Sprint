import { post } from './api.js';
import { $, setLoading, toast } from './utils.js';

function showPreview(preview) {
  const dialog = $('#privacyPreview');
  $('#previewPlace').textContent = `${preview.place_tag} 동네 아카이브`;
  $('#previewPre').textContent = preview.safe_pre_text || '공유할 내용 없음';
  $('#previewPost').textContent = preview.safe_post_text || '';
  $('#previewPostWrap').classList.toggle('hidden', !preview.safe_post_text);
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
  await post(`/cards/${cardId}/share-to-town`, { consent: true, place_tag: placeTag, preview_token: preview.preview_token });
  return true;
}

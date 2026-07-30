import { get, post, protectedImage } from './api.js';
import { $, emptyState, escapeHtml, formatDate, getUserId, placeOptions, setLoading, state, switchTab, toast } from './utils.js';
import { previewAndShare } from './privacy.js';

function draftKey() { return state.recallId ? `recall-draft:${getUserId()}:${state.recallId}` : null; }
function saveDraft() {
  const key = draftKey();
  if (!key) return;
  localStorage.setItem(key, JSON.stringify({
    initialAnswer: $('#initialAnswer').value,
    hintAnswer: $('#hintAnswer').value,
    hintLevel: state.hintLevel,
    additionalMemory: $('#additionalMemory').value,
  }));
  $('#draftStatus').textContent = '이 기기에 임시 저장됨';
}
function restoreDraft() {
  const key = draftKey();
  if (!key) return;
  try {
    const draft = JSON.parse(localStorage.getItem(key) || 'null');
    if (!draft) return;
    if (!$('#initialAnswer').value) $('#initialAnswer').value = draft.initialAnswer || '';
    if (draft.hintLevel) showHint(Math.min(Number(draft.hintLevel), maxHintLevel()));
    if (!$('#hintAnswer').value) $('#hintAnswer').value = draft.hintAnswer || '';
    if (!$('#additionalMemory').value) $('#additionalMemory').value = draft.additionalMemory || '';
    $('#draftStatus').textContent = '작성 중이던 내용을 복원했어요';
  } catch { localStorage.removeItem(key); }
}
function clearDraft() {
  const key = draftKey();
  if (key) localStorage.removeItem(key);
  $('#draftStatus').textContent = '';
}

function resetWorkspace() {
  $('#initialAnswer').value = ''; $('#hintAnswer').value = ''; $('#additionalMemory').value = '';
  $('#initialAnswer').disabled = false; $('#hintAnswer').disabled = false;
  $('#hintPanel').classList.add('hidden');
  $('#requestHint').disabled = false; $('#requestHint').textContent = '힌트 하나 받기';
  state.hintLevel = 0;
  state.hasHintAnswer = false;
  $('#originalBox').classList.add('hidden'); $('#additionalField').classList.add('hidden');
  $('#shareChoice').classList.add('hidden'); $('#completeRecall').classList.add('hidden');
  $('#completeRecall').innerHTML = state.recallStage > 1 ? '기존 추억 카드에 반영하기 <i>→</i>' : '추억 카드 완성하기 <i>→</i>';
  setRecallStage('answer');
}

export function closeRecallWorkspace() {
  const workspace = $('#recallWorkspace');
  if (!workspace || workspace.classList.contains('hidden')) return;

  // 탭을 떠나도 작성 내용은 브라우저 임시 저장소에 남겨 두고,
  // 화면 상태만 닫는다. 같은 기억의 '회상 시작'을 누르면 다시 복원된다.
  saveDraft();
  workspace.classList.add('hidden');
  $('#questionList').replaceChildren();
  $('#originalBox').replaceChildren();
  $('#shareAfterComplete').checked = false;
  $('#recallPlace').value = '';
  $('#recallPlace').disabled = true;
  resetWorkspace();
  state.recallId = null;
  state.recallStage = null;
  state.memoryId = null;
  state.recallQuestions = [];
}

function maxHintLevel() {
  return Math.max(0, state.recallQuestions.length - 1);
}

function showHint(level) {
  const maximum = maxHintLevel();
  if (!maximum) return;
  state.hintLevel = Math.min(Math.max(1, level), maximum);
  const hint = state.recallQuestions[state.hintLevel];
  $('#hintProgress').textContent = `회상 힌트 ${state.hintLevel}/${maximum}`;
  $('#hintText').textContent = hint?.question || '그날의 주변 분위기부터 천천히 떠올려 보세요.';
  $('#hintPanel').classList.remove('hidden');
  $('#requestHint').textContent = state.hintLevel < maximum ? '힌트 하나 더 받기' : '그래도 떠오르지 않아요';
  $('#hintPanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
  saveDraft();
}

function setRecallStage(stage) {
  const save = $('#saveAnswer');
  const reveal = $('#revealOriginal');
  const guide = $('#recallActionGuide');
  const progress = [...document.querySelectorAll('.progress > span')];
  progress.forEach((item, index) => item.classList.toggle('active', index <= ({ answer: 0, saved: 0, revealed: 1, completed: 2 }[stage] ?? 0)));

  if (stage === 'answer') {
    save.disabled = false; save.textContent = '떠오른 기억 저장하기';
    reveal.disabled = true; reveal.classList.remove('primary'); reveal.classList.add('secondary');
    $('#recallProgressLabel').textContent = '먼저 떠올리기';
    guide.innerHTML = '<b>먼저 지금 떠오르는 기억을 적어주세요.</b><span>답변을 저장하면 그날의 원본을 확인할 수 있어요.</span>';
  } else if (stage === 'saved') {
    save.disabled = true; save.textContent = '답변 저장됨 ✓';
    reveal.disabled = false; reveal.classList.remove('secondary'); reveal.classList.add('primary');
    $('#initialAnswer').disabled = true; $('#hintAnswer').disabled = true; $('#requestHint').disabled = true;
    $('#recallProgressLabel').textContent = '원본 확인하기';
    guide.innerHTML = '<b>지금의 기억을 안전하게 저장했어요.</b><span>이제 그날의 사진과 코멘트를 만나보세요.</span>';
  } else if (stage === 'revealed') {
    save.disabled = true; reveal.disabled = true;
    reveal.classList.remove('primary'); reveal.classList.add('secondary');
    $('#recallProgressLabel').textContent = '새 기억 더하기';
    guide.innerHTML = state.recallStage > 1
      ? '<b>원본을 다시 확인했어요.</b><span>이번에 떠오른 조각을 기존 추억 카드에 더해 주세요.</span>'
      : '<b>원본을 확인했어요.</b><span>새롭게 떠오른 조각을 더한 뒤 추억 카드를 완성해 주세요.</span>';
  }
}

export async function loadDue() {
  const list = $('#dueList');
  list.innerHTML = emptyState('◌', '기억을 불러오는 중이에요', '잠시만 기다려 주세요.');
  try {
    const items = await get('/recalls/due');
    $('#dueBadge').textContent = items.length; $('#dueBadge').classList.toggle('hidden', !items.length);
    if (!items.length) return list.innerHTML = emptyState('✓', '오늘의 회상을 모두 마쳤어요', '새로운 기억을 맡기거나 다음 회상 날을 기다려 주세요.');
    list.innerHTML = items.map((item) => {
      const sequence = item.same_day_count > 1 ? `<span class="sequence-chip">같은 날 ${item.day_sequence}/${item.same_day_count}번째 기억</span>` : '';
      const place = item.place_tag ? `${escapeHtml(item.place_tag)}에서 남긴 기억` : '그날의 장면이 기다리고 있어요';
      const cues = (item.cue_categories || []).map((cue) => `<span>${escapeHtml(cue)}</span>`).join('');
      return `<article class="due-card"><div><div class="meta">${escapeHtml(item.memory_date)} · ${item.stage}차 회상 ${sequence}</div><h3>${place}</h3><div class="cue-chips" aria-label="기억을 구분하는 단서">${cues}</div><p>${escapeHtml(item.prompt)}</p></div><button class="primary start-recall" data-memory-id="${item.memory_id}">회상 시작 <i>→</i></button></article>`;
    }).join('');
    list.querySelectorAll('.start-recall').forEach((button) => button.addEventListener('click', () => startRecall(button.dataset.memoryId)));
  } catch (error) { list.innerHTML = emptyState('!', '회상 목록을 불러오지 못했어요', error.message); }
}

async function startRecall(memoryId) {
  setLoading(true, '오늘의 질문을 고르고 있어요');
  try {
    let recall;
    try { recall = await post('/recalls', { memory_id: memoryId }); }
    catch (error) {
      const existingId = error.detail?.recall_id;
      if (!existingId) throw error;
      recall = await get(`/recalls/${existingId}`);
    }
    const data = recall.questions?.length ? recall : await post(`/recalls/${recall.id}/questions`);
    state.recallId = recall.id; state.recallStage = data.stage; state.memoryId = memoryId; resetWorkspace();
    state.recallQuestions = data.questions || [];
    state.hasHintAnswer = Boolean((data.hint_answers || []).length);
    const openingQuestion = state.recallQuestions[0];
    $('#questionList').innerHTML = openingQuestion ? `<div class="question"><b>먼저 떠올려 볼 질문</b><br>${escapeHtml(openingQuestion.question)}</div>` : '';
    if (data.hint_level > 0) {
      showHint(Math.min(data.hint_level, maxHintLevel()));
      const savedHint = [...(data.hint_answers || [])].reverse().find((item) => item.level === data.hint_level);
      $('#hintAnswer').value = savedHint?.answer || '';
    }
    if (data.initial_answer || data.memory_not_recalled || data.status === 'answered' || data.status === 'revealed') {
      $('#initialAnswer').value = data.initial_answer || '';
      setRecallStage('saved');
    }
    $('#recallWorkspace').classList.remove('hidden');
    if (data.status === 'revealed') {
      $('#additionalMemory').value = data.newly_recalled_text || '';
      await revealOriginal();
    }
    restoreDraft();
    $('#recallWorkspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
    toast('원본 없이 먼저 떠올려 보세요.');
  } catch (error) { toast(error.message, 'error'); } finally { setLoading(false); }
}

async function saveAnswer() {
  if (!state.recallId) return toast('먼저 회상을 시작해 주세요.', 'error');
  const answer = $('#initialAnswer').value.trim();
  const hintAnswer = $('#hintAnswer').value.trim();
  if (!answer && !hintAnswer) return toast('떠오르는 내용을 적거나 힌트를 하나 받아보세요.', 'error');
  setLoading(true, '지금 떠오른 기억을 안전하게 저장하고 있어요');
  try {
    await post(`/recalls/${state.recallId}/answers`, {
      initial_answer: answer || null,
      hint_answer: hintAnswer || null,
      hint_level: state.hintLevel,
      memory_not_recalled: false,
      finalize: true,
    });
    setRecallStage('saved');
    toast('답변을 저장했습니다. 이제 그날의 원본을 확인해 보세요.');
  } catch (error) { toast(error.message, 'error'); }
  finally { setLoading(false); }
}

async function requestHint() {
  if (!state.recallId) return toast('먼저 회상을 시작해 주세요.', 'error');
  const maximum = maxHintLevel();
  if (!maximum) return toast('이 기억에는 준비된 추가 힌트가 없어요.', 'error');

  if (state.hintLevel < maximum) {
    setLoading(true, '다음 회상 단서를 준비하고 있어요');
    try {
      const currentHintAnswer = $('#hintAnswer').value.trim();
      if (state.hintLevel > 0 && currentHintAnswer) {
        await post(`/recalls/${state.recallId}/answers`, {
          initial_answer: $('#initialAnswer').value.trim() || null,
          hint_answer: currentHintAnswer,
          hint_level: state.hintLevel,
          memory_not_recalled: false,
          finalize: false,
        });
        state.hasHintAnswer = true;
        $('#hintAnswer').value = '';
      }
      showHint(state.hintLevel + 1);
      toast('원본을 보여주지 않는 약한 단서를 열었어요.');
    } catch (error) { toast(error.message, 'error'); }
    finally { setLoading(false); }
    return;
  }

  setLoading(true, '지금까지의 회상 시도를 안전하게 남기고 있어요');
  try {
    const answer = $('#initialAnswer').value.trim();
    const hintAnswer = $('#hintAnswer').value.trim();
    await post(`/recalls/${state.recallId}/answers`, {
      initial_answer: answer || null,
      hint_answer: hintAnswer || null,
      hint_level: state.hintLevel,
      memory_not_recalled: !answer && !hintAnswer && !state.hasHintAnswer,
      finalize: true,
    });
    setRecallStage('saved');
    $('#recallActionGuide').innerHTML = '<b>충분히 천천히 떠올려 보았어요.</b><span>기억나지 않는 것도 자연스러운 일이에요. 이제 원본에서 다음 기억을 만나보세요.</span>';
    toast('회상 시도를 저장했습니다. 이제 그날의 원본을 확인할 수 있어요.');
  } catch (error) { toast(error.message, 'error'); }
  finally { setLoading(false); }
}

async function revealOriginal() {
  if (!state.recallId) return toast('먼저 회상을 시작해 주세요.', 'error');
  setLoading(true, '그날의 원본을 꺼내고 있어요');
  try {
    const original = await post(`/recalls/${state.recallId}/reveal`);
    let image = '';
    if (original.original_photo_url) {
      const src = await protectedImage(original.original_photo_url);
      image = `<img src="${src}" alt="원본 기억 사진" />`;
    }
    const place = original.place_label ? ` · ${escapeHtml(original.place_label)}` : '';
    $('#originalBox').innerHTML = `${image}<div class="meta">${formatDate(original.memory_date)}${place}</div><h3>${escapeHtml(original.title || '저장했던 기억')}</h3><p>${escapeHtml(original.original_comment)}</p>`;
    const suggestedPlace = original.place_tag || original.suggested_place_tag || '';
    if (suggestedPlace && state.placeTags.includes(suggestedPlace)) $('#recallPlace').value = suggestedPlace;
    $('#originalBox').classList.remove('hidden'); $('#additionalField').classList.remove('hidden');
    $('#shareChoice').classList.remove('hidden'); $('#completeRecall').classList.remove('hidden');
    setRecallStage('revealed');
    $('#originalBox').scrollIntoView({ behavior: 'smooth', block: 'center' });
    toast('원본을 만났어요. 새롭게 떠오른 조각을 더해 보세요.');
  } catch (error) { toast(error.message, 'error'); } finally { setLoading(false); }
}

async function completeRecall() {
  if (!state.recallId) return;
  setLoading(true, '회상 조각을 한 편의 추억으로 잇고 있어요');
  try {
    const card = await post(`/recalls/${state.recallId}/complete`, { additional_memory: $('#additionalMemory').value });
    state.latestCardId = card.id;
    let shareWarning = null;
    if ($('#shareAfterComplete').checked) {
      const placeTag = $('#recallPlace').value;
      if (!placeTag) shareWarning = '장소를 고르지 않아 동네 공유는 건너뛰었습니다.';
      else if (!state.placeTags.includes(placeTag)) shareWarning = '표준 지역 목록에 없는 장소라 동네 공유는 건너뛰었습니다.';
      else {
        try {
          setLoading(false);
          if (!await previewAndShare(card.id, placeTag)) shareWarning = '카드는 완성했고, 동네 공유는 취소했습니다.';
        }
        catch (error) { shareWarning = `카드는 완성했지만 동네 공유는 실패했어요: ${error.message}`; }
      }
    }
    const updatedExistingCard = state.recallStage > 1;
    clearDraft();
    state.recallId = null; state.recallStage = null; $('#recallWorkspace').classList.add('hidden');
    toast(shareWarning || (updatedExistingCard ? `‘${card.card_title}’ 카드에 이번 회상을 반영했습니다.` : `‘${card.card_title}’ 카드가 완성되었습니다.`), shareWarning ? 'error' : 'normal');
    document.dispatchEvent(new CustomEvent('cardcreated'));
    switchTab('cards');
  } catch (error) { toast(error.message, 'error'); document.dispatchEvent(new CustomEvent('cardcreated')); } finally { setLoading(false); }
}

export function initRecall() {
  $('#refreshDue').addEventListener('click', loadDue);
  $('#saveAnswer').addEventListener('click', saveAnswer);
  $('#requestHint').addEventListener('click', requestHint);
  $('#revealOriginal').addEventListener('click', revealOriginal);
  $('#completeRecall').addEventListener('click', completeRecall);
  $('#shareAfterComplete').addEventListener('change', (event) => $('#recallPlace').disabled = !event.target.checked);
  $('#recallPlace').disabled = true;
  ['initialAnswer', 'hintAnswer', 'additionalMemory'].forEach((id) => $(`#${id}`).addEventListener('input', saveDraft));
  setRecallStage('answer');
}

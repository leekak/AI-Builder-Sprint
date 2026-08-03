import { $, USER_ID_KEY, toast } from './utils.js';

function applyState(loggedIn) {
  $('#userId').readOnly = loggedIn;
  $('#userSessionButton').textContent = loggedIn ? '로그아웃' : '로그인';
  $('#userSessionButton').classList.toggle('active-user', loggedIn);
}

function login() {
  const input = $('#userId');
  const id = input.value.trim();
  if (!id) return toast('사용자 아이디를 입력해주세요.', 'error');
  localStorage.setItem(USER_ID_KEY, id);
  applyState(true);
  toast(`${id}(으)로 로그인했습니다.`);
  document.dispatchEvent(new CustomEvent('userchange'));
}

function logout() {
  localStorage.removeItem(USER_ID_KEY);
  $('#userId').value = '';
  applyState(false);
  toast('로그아웃했습니다.');
  document.dispatchEvent(new CustomEvent('userchange'));
}

export function initUserSession() {
  const saved = localStorage.getItem(USER_ID_KEY);
  $('#userId').value = saved || '';
  applyState(Boolean(saved));
  $('#userSessionButton').addEventListener('click', () => {
    if ($('#userId').readOnly) logout();
    else login();
  });
}

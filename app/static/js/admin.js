import { adminPost, get, isAdmin, setAdminToken } from './api.js';
import { $, switchTab, toast } from './utils.js';

function renderAdminState() {
  const button = $('#adminSessionButton');
  const active = isAdmin();
  button.textContent = active ? '관리자 로그아웃' : '관리자 로그인';
  button.classList.toggle('active-admin', active);
  document.body.classList.toggle('admin-mode', active);
  // 관리자 계정은 동네 추억 카드 검열 전용이라, 로그인하는 순간 다른 탭은 숨기고 이 화면으로 고정한다.
  // 일반 사용자의 새로고침 시 마지막 탭(URL 해시)을 그대로 유지하기 위해, 로그아웃 시에는 강제로 옮기지 않는다.
  if (active) switchTab('town');
}

async function verifyStoredSession() {
  if (!isAdmin()) return renderAdminState();
  try {
    await get('/admin/me', { headers: { Authorization: `Bearer ${sessionStorage.getItem('memory-recall-admin-token')}` } });
  } catch {
    setAdminToken('');
  }
  renderAdminState();
}

async function login(event) {
  event.preventDefault();
  try {
    const session = await adminPost('/admin/login', {
      username: $('#adminUsername').value.trim(),
      password: $('#adminPassword').value,
    });
    setAdminToken(session.access_token);
    $('#adminPassword').value = '';
    $('#adminLoginDialog').close();
    renderAdminState();
    document.dispatchEvent(new CustomEvent('adminchange'));
    toast(`${session.username} 관리자로 로그인했습니다.`);
  } catch (error) { toast(error.message, 'error'); }
}

export function initAdmin() {
  $('#adminSessionButton').addEventListener('click', () => {
    if (isAdmin()) {
      setAdminToken('');
      renderAdminState();
      document.dispatchEvent(new CustomEvent('adminchange'));
      toast('관리자 세션에서 로그아웃했습니다.');
      return;
    }
    $('#adminLoginDialog').showModal();
    $('#adminUsername').focus();
  });
  $('#cancelAdminLogin').addEventListener('click', () => $('#adminLoginDialog').close());
  $('#adminLoginForm').addEventListener('submit', login);
  verifyStoredSession();
}

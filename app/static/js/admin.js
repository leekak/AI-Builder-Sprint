import { adminPost, get, isAdmin, setAdminToken } from './api.js';
import { $, toast } from './utils.js';

function renderAdminState() {
  const button = $('#adminSessionButton');
  const active = isAdmin();
  button.textContent = active ? '관리자 로그아웃' : '관리자 로그인';
  button.classList.toggle('active-admin', active);
  document.body.classList.toggle('admin-mode', active);
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

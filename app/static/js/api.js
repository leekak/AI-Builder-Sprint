import { getUserId } from './utils.js';

const ADMIN_TOKEN_KEY = 'memory-recall-admin-token';

export function getAdminToken() {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY) || '';
}

export function setAdminToken(token) {
  if (token) sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  else sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function isAdmin() {
  return Boolean(getAdminToken());
}

function requestHeaders(json = false) {
  const result = { 'X-User-Id': getUserId() };
  if (json) result['Content-Type'] = 'application/json';
  return result;
}

function errorMessage(body, status) {
  const detail = body?.detail ?? body;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(', ');
  return `요청을 처리하지 못했습니다. (${status})`;
}

export async function api(path, options = {}) {
  const response = await fetch(path, options);
  const type = response.headers.get('content-type') || '';
  const body = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(errorMessage(body, response.status));
    error.status = response.status;
    error.detail = body?.detail;
    throw error;
  }
  return body;
}

export function get(path, options = {}) {
  return api(path, { ...options, headers: { ...requestHeaders(), ...(options.headers || {}) } });
}

export function post(path, body, options = {}) {
  return api(path, {
    method: 'POST',
    ...options,
    headers: { ...requestHeaders(body !== undefined), ...(options.headers || {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function patch(path, body, options = {}) {
  return api(path, {
    method: 'PATCH', ...options,
    headers: { ...requestHeaders(true), ...(options.headers || {}) },
    body: JSON.stringify(body),
  });
}

export function postForm(path, formData) {
  return api(path, { method: 'POST', headers: requestHeaders(), body: formData });
}

export function del(path, options = {}) {
  return api(path, { method: 'DELETE', ...options, headers: { ...requestHeaders(), ...(options.headers || {}) } });
}

function adminHeaders(json = false) {
  const token = getAdminToken();
  const headers = requestHeaders(json);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export function adminPost(path, body) {
  return api(path, {
    method: 'POST',
    headers: adminHeaders(body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function adminDelete(path) {
  return api(path, { method: 'DELETE', headers: adminHeaders() });
}

export async function protectedImage(url) {
  const response = await fetch(url, { headers: requestHeaders() });
  if (!response.ok) throw new Error('사진을 불러오지 못했습니다.');
  return URL.createObjectURL(await response.blob());
}

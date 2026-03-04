/**
 * API Client for Support Form
 * All requests include a JWT Bearer token from localStorage when present.
 */

const API_BASE = typeof window !== 'undefined'
  ? (window.API_BASE || 'http://127.0.0.1:8000')
  : 'http://127.0.0.1:8000';

/** Return the stored JWT token, or null */
function getAuthToken() {
  try {
    return localStorage.getItem('auth_token') || null;
  } catch {
    return null;
  }
}

/** Build common headers including Authorization when a token is present */
function authHeaders(extra = {}) {
  const headers = { 'Content-Type': 'application/json', ...extra };
  const token = getAuthToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

/**
 * Sign up a new user.
 * @param {{ name: string, email: string, password: string }} body
 * @returns {Promise<{ access_token: string, user: object }>}
 */
export async function signup(body) {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Signup failed');
  }
  return res.json();
}

/**
 * Log in an existing user.
 * @param {{ email: string, password: string }} body
 * @returns {Promise<{ access_token: string, user: object }>}
 */
export async function login(body) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Login failed');
  }
  return res.json();
}

/**
 * Submit the support form.
 * Sends the JWT token if the user is signed in.
 *
 * @param {{ name: string, email: string, subject: string,
 *           category: string, priority: string, message: string }} formData
 * @returns {Promise<{ ticket_id: string, message: string, estimated_response_time: string }>}
 */
export async function submitSupportForm(formData) {
  const res = await fetch(`${API_BASE}/api/support/submit`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(formData),
  });

  if (!res.ok) {
    const error = await res.json();
    const detail = error.detail;
    let msg = 'Submission failed. Please try again.';
    if (Array.isArray(detail))          msg = detail.map(d => d.msg).join(', ');
    else if (typeof detail === 'string') msg = detail;
    throw new Error(msg);
  }

  return res.json();   // { ticket_id, message, estimated_response_time }
}

/**
 * Fetch ticket status and conversation history.
 * Sends the JWT token so authenticated users can see their own tickets.
 *
 * @param {string} ticketId
 * @returns {Promise<{ ticket_id: string, status: string, messages: Array, created_at: string, last_updated: string }>}
 */
export async function getTicketStatus(ticketId) {
  const res = await fetch(`${API_BASE}/api/support/ticket/${encodeURIComponent(ticketId)}`, {
    method: 'GET',
    headers: authHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Ticket not found');
  }

  return res.json();
}

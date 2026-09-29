const API_BASE = 'https://ecommerce-onsq.onrender.com/api';

async function apiFetch(endpoint, options = {}) {
  const token = localStorage.getItem('volta_token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

const API = {
  // Products
  getProducts: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return apiFetch(`/products${q ? '?' + q : ''}`);
  },
  getProduct: (id) => apiFetch(`/products/${id}`),
  getCategories: () => apiFetch('/categories'),

  // Auth
  register: (data) => apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => apiFetch('/auth/me'),

  // Orders
  createOrder: (data) => apiFetch('/orders', { method: 'POST', body: JSON.stringify(data) }),
  getOrders: () => apiFetch('/orders'),
  getOrder: (id) => apiFetch(`/orders/${id}`),

  // Reviews
  addReview: (productId, data) => apiFetch(`/products/${productId}/reviews`, {
    method: 'POST', body: JSON.stringify(data)
  }),
};

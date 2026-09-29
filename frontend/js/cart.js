const Cart = {
  items: [],

  load() {
    try { this.items = JSON.parse(localStorage.getItem('volta_cart') || '[]'); }
    catch { this.items = []; }
    this.updateUI();
  },

  save() {
    localStorage.setItem('volta_cart', JSON.stringify(this.items));
    this.updateUI();
  },

  add(product, qty = 1) {
    const existing = this.items.find(i => i.id === product.id);
    if (existing) {
      existing.quantity = Math.min(existing.quantity + qty, product.stock || 99);
    } else {
      this.items.push({ ...product, quantity: qty });
    }
    this.save();
    showToast(`${product.name} added to cart`, 'success');
    const badge = document.getElementById('cartCount');
    if (badge) { badge.classList.add('pop'); setTimeout(() => badge.classList.remove('pop'), 300); }
  },

  remove(id) {
    this.items = this.items.filter(i => i.id !== id);
    this.save();
  },

  updateQty(id, qty) {
    const item = this.items.find(i => i.id === id);
    if (item) {
      if (qty <= 0) this.remove(id);
      else item.quantity = qty;
    }
    this.save();
  },

  clear() { this.items = []; this.save(); },

  get count() { return this.items.reduce((s, i) => s + i.quantity, 0); },
  get total() { return this.items.reduce((s, i) => s + i.price * i.quantity, 0); },

  updateUI() {
    const el = document.getElementById('cartCount');
    if (el) el.textContent = this.count;
  }
};

// Initialize cart on load
Cart.load();

function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast show ' + type;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3000);
}

function renderStars(rating, interactive = false, size = 14) {
  if (interactive) {
    return Array.from({length: 5}, (_, i) =>
      `<button class="star-btn ${i < (rating || 0) ? 'active' : ''}" data-val="${i+1}" onclick="setRating(${i+1})">★</button>`
    ).join('');
  }
  const full = Math.floor(rating);
  const half = rating % 1 >= 0.5;
  let stars = '★'.repeat(full);
  if (half) stars += '½';
  stars += '☆'.repeat(5 - full - (half ? 1 : 0));
  return `<span class="stars" style="font-size:${size}px">${stars}</span>`;
}

function formatPrice(p) { return '$' + Number(p).toFixed(2); }

function formatDate(d) {
  return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

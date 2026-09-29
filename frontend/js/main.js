let currentPage = 1;
let currentCategory = 'all';
let currentSort = 'newest';
let currentSearch = '';
let searchDebounce;

// Update auth nav for index page (paths differ)
if (Auth.user) {
  const menu = document.getElementById('authMenu');
  if (menu) {
    menu.innerHTML = `
      <span class="user-greeting">Hi, <strong>${Auth.user.name.split(' ')[0]}</strong></span>
      <button class="btn-auth" onclick="window.location.href='pages/orders.html'">Orders</button>
      <button class="btn-auth" onclick="Auth.logout()">Sign out</button>
    `;
  }
} else {
  const menu = document.getElementById('authMenu');
  if (menu) {
    menu.innerHTML = `
      <button class="btn-auth" onclick="window.location.href='pages/login.html'">Sign in</button>
      <button class="btn-auth primary" onclick="window.location.href='pages/register.html'">Register</button>
    `;
  }
}

// Update cart icon href for index page
const cartBtn = document.getElementById('cartBtn');
if (cartBtn) cartBtn.href = 'pages/cart.html';

async function loadCategories() {
  try {
    const cats = await API.getCategories();
    const pills = document.getElementById('categoryPills');
    cats.forEach(c => {
      const btn = document.createElement('button');
      btn.className = 'cat-pill';
      btn.dataset.slug = c.slug;
      btn.textContent = `${c.name} (${c.product_count})`;
      btn.onclick = () => filterCategory(c.slug, btn);
      pills.appendChild(btn);
    });
  } catch(e) { console.error(e); }
}

function filterCategory(slug, btn) {
  currentCategory = slug;
  currentPage = 1;
  document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  loadProducts();
}

function applySorting() {
  currentSort = document.getElementById('sortSelect').value;
  currentPage = 1;
  loadProducts();
}

function applySearch() {
  currentSearch = document.getElementById('searchInput').value.trim();
  currentPage = 1;
  loadProducts();
}

document.getElementById('searchInput')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') applySearch();
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(applySearch, 500);
});

async function loadProducts() {
  const grid = document.getElementById('productsGrid');
  grid.innerHTML = '<div class="loading-spinner"></div>';

  try {
    const params = { page: currentPage, sort: currentSort, limit: 12 };
    if (currentCategory !== 'all') params.category = currentCategory;
    if (currentSearch) params.search = currentSearch;

    const data = await API.getProducts(params);

    const title = document.getElementById('sectionTitle');
    title.textContent = currentSearch
      ? `Results for "${currentSearch}" (${data.total})`
      : currentCategory !== 'all'
      ? data.products[0]?.category_name || 'Products'
      : `All Products (${data.total})`;

    if (data.products.length === 0) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:60px 24px;color:var(--text-muted)">
          <div style="font-size:48px;margin-bottom:16px">🔍</div>
          <h3 style="margin-bottom:8px">No products found</h3>
          <p>Try adjusting your search or filters.</p>
        </div>`;
      document.getElementById('pagination').innerHTML = '';
      return;
    }

    grid.innerHTML = data.products.map(p => productCard(p)).join('');
    renderPagination(data.page, data.pages);
  } catch(e) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">
      Failed to load products. Make sure the server is running on port 5000.
    </div>`;
  }
}

function productCard(p) {
  const discount = p.original_price
    ? Math.round((1 - p.price / p.original_price) * 100)
    : null;
  const badgeClass = p.badge === 'Sale' ? 'badge-sale'
    : p.badge === 'New' ? 'badge-new'
    : p.badge === 'Best Seller' ? 'badge-bestseller' : '';

  return `
  <div class="product-card" onclick="window.location.href='pages/product.html?id=${p.id}'">
    <div class="product-image-wrap">
      <img src="${p.image_url}" alt="${p.name}" loading="lazy" onerror="this.src='https://via.placeholder.com/400x300/161b27/6c63ff?text=Product'">
      ${p.badge ? `<span class="product-badge ${badgeClass}">${p.badge}</span>` : ''}
      <button class="quick-add" onclick="event.stopPropagation(); quickAdd(${p.id}, '${p.name.replace(/'/g,"\\'")}', ${p.price}, '${p.image_url}', ${p.stock})">
        + Add to Cart
      </button>
    </div>
    <div class="product-info">
      <div class="product-category">${p.category_name || ''}</div>
      <div class="product-name">${p.name}</div>
      <div class="product-rating">
        ${renderStars(p.rating)}
        <span class="rating-count">(${p.review_count})</span>
      </div>
      <div class="product-price">
        <span class="price-current">${formatPrice(p.price)}</span>
        ${p.original_price ? `<span class="price-original">${formatPrice(p.original_price)}</span>` : ''}
        ${discount ? `<span class="price-discount">-${discount}%</span>` : ''}
      </div>
    </div>
  </div>`;
}

function quickAdd(id, name, price, image_url, stock) {
  Cart.add({ id, name, price, image_url, stock });
}

function renderPagination(page, pages) {
  const el = document.getElementById('pagination');
  if (pages <= 1) { el.innerHTML = ''; return; }

  let html = '';
  if (page > 1) html += `<button class="page-btn" onclick="goPage(${page-1})">‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || (i >= page - 1 && i <= page + 1)) {
      html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="goPage(${i})">${i}</button>`;
    } else if (i === page - 2 || i === page + 2) {
      html += `<span class="page-btn" style="border:none;background:none">…</span>`;
    }
  }
  if (page < pages) html += `<button class="page-btn" onclick="goPage(${page+1})">›</button>`;
  el.innerHTML = html;
}

function goPage(p) {
  currentPage = p;
  loadProducts();
  document.getElementById('products-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Init
loadCategories();
loadProducts();

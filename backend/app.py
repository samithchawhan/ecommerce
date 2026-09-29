import sqlite3
import hashlib
import hmac
import os
import json
import jwt
import datetime
from flask import Flask, request, jsonify, g
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ecommerce-secret-key-change-in-production'
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'ecommerce.db')

# ─── CORS ─────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'message': 'E-commerce API is running'})

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return jsonify({}), 200

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'customer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            original_price REAL,
            image_url TEXT,
            category_id INTEGER,
            stock INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            badge TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            shipping_name TEXT,
            shipping_address TEXT,
            shipping_city TEXT,
            shipping_zip TEXT,
            payment_method TEXT DEFAULT 'card',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')

    # Seed categories
    cats = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if cats == 0:
        db.executemany("INSERT INTO categories (name, slug) VALUES (?, ?)", [
            ('Electronics', 'electronics'),
            ('Clothing', 'clothing'),
            ('Books', 'books'),
            ('Home & Garden', 'home-garden'),
            ('Sports', 'sports'),
        ])

    # Seed products
    prods = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if prods == 0:
        products = [
            ('Wireless Pro Headphones', 'Premium noise-cancelling wireless headphones with 40hr battery life. Crystal-clear sound with deep bass and Bluetooth 5.3 connectivity. Foldable design with memory foam ear cushions.', 89.99, 129.99, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400', 1, 50, 4.8, 312, 'Best Seller'),
            ('Ultra-Thin Laptop 15"', 'Powerful ultra-thin laptop with Intel i7 12th Gen, 16GB RAM, 512GB NVMe SSD. 15.6" IPS display, all-day battery, backlit keyboard. Perfect for professionals and students.', 899.00, 1099.00, 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400', 1, 25, 4.6, 98, 'Sale'),
            ('Smart Watch Series X', 'Advanced smartwatch with health monitoring, GPS, ECG, SpO2. 7-day battery, 50m water resistance, customizable faces. Compatible with iOS and Android.', 249.99, None, 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400', 1, 80, 4.5, 445, 'New'),
            ('4K Mirrorless Camera', 'Professional 24MP mirrorless camera, 4K video, 5-axis stabilization. Wi-Fi, dual card slots, weather-sealed body. Includes 18-55mm kit lens.', 1299.00, 1499.00, 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=400', 1, 15, 4.9, 67, 'Sale'),
            ('Mechanical Keyboard RGB', 'TKL mechanical keyboard with Cherry MX switches, RGB per-key lighting, aluminum frame. N-key rollover, USB-C detachable cable, PBT keycaps.', 129.99, None, 'https://images.unsplash.com/photo-1541140532154-b024d705b90a?w=400', 1, 60, 4.7, 234, None),
            ('Premium Cotton Hoodie', 'Ultra-soft 380GSM premium cotton blend hoodie. Kangaroo pocket, ribbed cuffs, adjustable drawstring. Pre-shrunk fabric, machine washable. Sizes XS–3XL.', 64.99, 89.99, 'https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=400', 2, 200, 4.4, 567, 'Sale'),
            ('Slim Fit Chinos', 'Modern slim-fit chinos in stretch twill fabric. 4-way stretch for comfort, wrinkle-resistant finish. Available in 8 colors. Machine washable.', 49.99, None, 'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=400', 2, 150, 4.3, 189, None),
            ('Running Shoes Air Max', 'Lightweight running shoes with responsive Air cushioning, engineered mesh upper, rubber outsole. Suitable for road and trail. Reflective details for night safety.', 119.99, 149.99, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400', 5, 90, 4.6, 723, 'Best Seller'),
            ('Python Deep Dive', 'Comprehensive guide to Python from beginner to expert. Covers data structures, OOP, async programming, testing, and deployment. 800+ pages with exercises.', 39.99, 54.99, 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=400', 3, 300, 4.8, 1204, 'Best Seller'),
            ('The Art of System Design', 'Master large-scale system design interviews and real-world architecture. Covers distributed systems, databases, caching, load balancing. Written by senior engineers at FAANG.', 44.99, None, 'https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=400', 3, 200, 4.9, 876, 'New'),
            ('Ergonomic Office Chair', 'Premium mesh ergonomic chair with lumbar support, adjustable armrests, headrest, and seat depth. Weight capacity 300lbs. 5-year warranty. Easy assembly.', 349.99, 499.99, 'https://images.unsplash.com/photo-1592078615290-033ee584e267?w=400', 4, 30, 4.5, 312, 'Sale'),
            ('Yoga Mat Premium', 'Extra-thick 6mm eco-friendly yoga mat with alignment lines, non-slip texture both sides. Comes with carry strap. 72"x26". Odor-free TPE material.', 44.99, None, 'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400', 5, 120, 4.7, 445, None),
        ]
        db.executemany('''INSERT INTO products 
            (name, description, price, original_price, image_url, category_id, stock, rating, review_count, badge)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', products)

    db.commit()
    db.close()
    print("✅ Database initialized")

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────
def hash_password(password):
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def check_password(password, stored):
    try:
        salt, hashed = stored.split(':')
        return hmac.compare_digest(
            hashlib.sha256((salt + password).encode()).hexdigest(),
            hashed
        )
    except:
        return False

def generate_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            g.current_user = data
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

def row_to_dict(row):
    return dict(row) if row else None

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return jsonify({'error': 'All fields required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    pw_hash = hash_password(password)
    cursor = db.execute('INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)',
                        (name, email, pw_hash))
    db.commit()
    user_id = cursor.lastrowid
    token = generate_token(user_id, 'customer')
    return jsonify({'token': token, 'user': {'id': user_id, 'name': name, 'email': email, 'role': 'customer'}}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not user or not check_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = generate_token(user['id'], user['role'])
    return jsonify({'token': token, 'user': {
        'id': user['id'], 'name': user['name'],
        'email': user['email'], 'role': user['role']
    }})

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    db = get_db()
    user = db.execute('SELECT id, name, email, role, created_at FROM users WHERE id = ?',
                      (g.current_user['user_id'],)).fetchone()
    return jsonify(row_to_dict(user))

# ─── PRODUCT ROUTES ───────────────────────────────────────────────────────────
@app.route('/api/products', methods=['GET'])
def get_products():
    db = get_db()
    category = request.args.get('category')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'created_at')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 12))
    offset = (page - 1) * limit

    base_query = '''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.stock > 0
    '''
    params = []

    if category and category != 'all':
        base_query += ' AND c.slug = ?'
        params.append(category)
    if search:
        base_query += ' AND (p.name LIKE ? OR p.description LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    sort_map = {
        'price_asc': 'p.price ASC',
        'price_desc': 'p.price DESC',
        'rating': 'p.rating DESC',
        'newest': 'p.created_at DESC',
    }
    base_query += f' ORDER BY {sort_map.get(sort, "p.created_at DESC")}'

    total = db.execute(f'SELECT COUNT(*) FROM ({base_query})', params).fetchone()[0]
    products = db.execute(base_query + ' LIMIT ? OFFSET ?', params + [limit, offset]).fetchall()

    return jsonify({
        'products': [dict(p) for p in products],
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit
    })

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    db = get_db()
    product = db.execute('''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM products p LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    ''', (product_id,)).fetchone()

    if not product:
        return jsonify({'error': 'Product not found'}), 404

    reviews = db.execute('''
        SELECT r.*, u.name as user_name FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = ? ORDER BY r.created_at DESC LIMIT 10
    ''', (product_id,)).fetchall()

    related = db.execute('''
        SELECT * FROM products WHERE category_id = ? AND id != ? AND stock > 0 LIMIT 4
    ''', (product['category_id'], product_id)).fetchall()

    return jsonify({
        'product': dict(product),
        'reviews': [dict(r) for r in reviews],
        'related': [dict(r) for r in related]
    })

@app.route('/api/categories', methods=['GET'])
def get_categories():
    db = get_db()
    cats = db.execute('''
        SELECT c.*, COUNT(p.id) as product_count
        FROM categories c LEFT JOIN products p ON c.id = p.category_id AND p.stock > 0
        GROUP BY c.id
    ''').fetchall()
    return jsonify([dict(c) for c in cats])

# ─── CART / ORDER ROUTES ──────────────────────────────────────────────────────
@app.route('/api/orders', methods=['POST'])
@token_required
def create_order():
    data = request.get_json()
    items = data.get('items', [])
    shipping = data.get('shipping', {})

    if not items:
        return jsonify({'error': 'Cart is empty'}), 400

    db = get_db()
    total = 0
    validated_items = []

    for item in items:
        product = db.execute('SELECT * FROM products WHERE id = ?', (item['product_id'],)).fetchone()
        if not product:
            return jsonify({'error': f'Product {item["product_id"]} not found'}), 404
        if product['stock'] < item['quantity']:
            return jsonify({'error': f'Insufficient stock for {product["name"]}'}), 400
        total += product['price'] * item['quantity']
        validated_items.append({'product': dict(product), 'quantity': item['quantity']})

    cursor = db.execute('''
        INSERT INTO orders (user_id, total, status, shipping_name, shipping_address, shipping_city, shipping_zip, payment_method)
        VALUES (?, ?, 'processing', ?, ?, ?, ?, ?)
    ''', (g.current_user['user_id'], round(total, 2),
          shipping.get('name', ''), shipping.get('address', ''),
          shipping.get('city', ''), shipping.get('zip', ''),
          data.get('payment_method', 'card')))

    order_id = cursor.lastrowid

    for item in validated_items:
        db.execute('INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)',
                   (order_id, item['product']['id'], item['quantity'], item['product']['price']))
        db.execute('UPDATE products SET stock = stock - ? WHERE id = ?',
                   (item['quantity'], item['product']['id']))

    db.commit()
    return jsonify({'order_id': order_id, 'total': round(total, 2), 'status': 'processing'}), 201

@app.route('/api/orders', methods=['GET'])
@token_required
def get_orders():
    db = get_db()
    orders = db.execute('''
        SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC
    ''', (g.current_user['user_id'],)).fetchall()

    result = []
    for order in orders:
        order_dict = dict(order)
        items = db.execute('''
            SELECT oi.*, p.name, p.image_url FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (order['id'],)).fetchall()
        order_dict['items'] = [dict(i) for i in items]
        result.append(order_dict)

    return jsonify(result)

@app.route('/api/orders/<int:order_id>', methods=['GET'])
@token_required
def get_order(order_id):
    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?',
                       (order_id, g.current_user['user_id'])).fetchone()
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    items = db.execute('''
        SELECT oi.*, p.name, p.image_url FROM order_items oi
        JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()

    order_dict = dict(order)
    order_dict['items'] = [dict(i) for i in items]
    return jsonify(order_dict)

# ─── REVIEWS ──────────────────────────────────────────────────────────────────
@app.route('/api/products/<int:product_id>/reviews', methods=['POST'])
@token_required
def add_review(product_id):
    data = request.get_json()
    rating = int(data.get('rating', 0))
    comment = data.get('comment', '').strip()

    if not 1 <= rating <= 5:
        return jsonify({'error': 'Rating must be 1-5'}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM reviews WHERE product_id = ? AND user_id = ?',
                          (product_id, g.current_user['user_id'])).fetchone()
    if existing:
        return jsonify({'error': 'Already reviewed this product'}), 409

    db.execute('INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)',
               (product_id, g.current_user['user_id'], rating, comment))

    # Update product rating
    avg = db.execute('SELECT AVG(rating), COUNT(*) FROM reviews WHERE product_id = ?',
                     (product_id,)).fetchone()
    db.execute('UPDATE products SET rating = ?, review_count = ? WHERE id = ?',
               (round(avg[0], 1), avg[1], product_id))
    db.commit()
    return jsonify({'message': 'Review added'}), 201

# ─── HEALTH ───────────────────────────────────────────────────────────────────
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.datetime.utcnow().isoformat()})

if __name__ == '__main__':
    init_db()
    app.run()

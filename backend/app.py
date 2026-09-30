import datetime
import hashlib
import hmac
import os
import sqlite3
from functools import wraps

import jwt
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MONGODB_URI'] = os.getenv('MONGODB_URI')
app.config['MONGODB_DATABASE'] = os.getenv('MONGODB_DATABASE', 'ecommerce')
app.config['SQLITE_DATABASE'] = os.path.join(os.path.dirname(__file__), 'ecommerce.db')

_mongo_client = None


def get_db():
    global _mongo_client
    if not app.config['MONGODB_URI']:
        raise RuntimeError('Set MONGODB_URI in backend/.env or the deployment environment.')
    if _mongo_client is None:
        _mongo_client = MongoClient(app.config['MONGODB_URI'])
    return _mongo_client[app.config['MONGODB_DATABASE']]


def serialize(value):
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != '_id'}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return value


def next_id(db, name):
    counter = db.counters.find_one_and_update(
        {'_id': name},
        {'$inc': {'value': 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return counter['value']


def migrate_sqlite(db):
    path = app.config['SQLITE_DATABASE']
    if not os.path.exists(path):
        return

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        categories = [dict(row) for row in connection.execute('SELECT * FROM categories')]
        products = [dict(row) for row in connection.execute('SELECT * FROM products')]
        users = [dict(row) for row in connection.execute('SELECT * FROM users')]
        orders = [dict(row) for row in connection.execute('SELECT * FROM orders')]
        order_items = [dict(row) for row in connection.execute('SELECT * FROM order_items')]
        reviews = [dict(row) for row in connection.execute('SELECT * FROM reviews')]
    finally:
        connection.close()

    for collection_name, documents in (
        ('categories', categories),
        ('products', products),
        ('users', users),
        ('reviews', reviews),
    ):
        for document in documents:
            created_at = document.get('created_at')
            if isinstance(created_at, str):
                try:
                    document['created_at'] = datetime.datetime.fromisoformat(created_at)
                except ValueError:
                    pass
            db[collection_name].update_one(
                {'id': document['id']}, {'$setOnInsert': document}, upsert=True
            )

    items_by_order = {}
    for item in order_items:
        items_by_order.setdefault(item['order_id'], []).append(item)
    for order in orders:
        created_at = order.get('created_at')
        if isinstance(created_at, str):
            try:
                order['created_at'] = datetime.datetime.fromisoformat(created_at)
            except ValueError:
                pass
        order['items'] = items_by_order.get(order['id'], [])
        db.orders.update_one({'id': order['id']}, {'$setOnInsert': order}, upsert=True)


def init_db():
    if not app.config['SECRET_KEY']:
        raise RuntimeError('Set SECRET_KEY in backend/.env or the deployment environment.')

    db = get_db()
    _mongo_client.admin.command('ping')
    db.users.create_index([('id', ASCENDING)], unique=True)
    db.users.create_index([('email', ASCENDING)], unique=True)
    db.categories.create_index([('id', ASCENDING)], unique=True)
    db.categories.create_index([('slug', ASCENDING)], unique=True)
    db.products.create_index([('id', ASCENDING)], unique=True)
    db.products.create_index([('category_id', ASCENDING), ('stock', ASCENDING)])
    db.orders.create_index([('id', ASCENDING)], unique=True)
    db.orders.create_index([('user_id', ASCENDING), ('created_at', -1)])
    db.reviews.create_index([('id', ASCENDING)], unique=True)
    db.reviews.create_index([('product_id', ASCENDING), ('user_id', ASCENDING)], unique=True)

    collections = ('users', 'categories', 'products', 'orders', 'reviews')
    if all(db[name].count_documents({}) == 0 for name in collections):
        migrate_sqlite(db)

    seed_categories = [
        {'id': 1, 'name': 'Electronics', 'slug': 'electronics'},
        {'id': 2, 'name': 'Clothing', 'slug': 'clothing'},
        {'id': 3, 'name': 'Books', 'slug': 'books'},
        {'id': 4, 'name': 'Home & Garden', 'slug': 'home-garden'},
        {'id': 5, 'name': 'Sports', 'slug': 'sports'},
    ]
    if db.categories.count_documents({}) == 0:
        db.categories.insert_many(seed_categories)

    if db.products.count_documents({}) == 0:
        now = datetime.datetime.utcnow()
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
        db.products.insert_many([
            {
                'id': index,
                'name': product[0],
                'description': product[1],
                'price': product[2],
                'original_price': product[3],
                'image_url': product[4],
                'category_id': product[5],
                'stock': product[6],
                'rating': product[7],
                'review_count': product[8],
                'badge': product[9],
                'created_at': now,
            }
            for index, product in enumerate(products, start=1)
        ])

    for name in collections:
        maximum = db[name].find_one(sort=[('id', -1)])
        if maximum:
            db.counters.update_one(
                {'_id': name}, {'$max': {'value': maximum['id']}}, upsert=True
            )


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


def hash_password(password):
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f'{salt}:{hashed}'


def check_password(password, stored):
    try:
        salt, hashed = stored.split(':')
        return hmac.compare_digest(
            hashlib.sha256((salt + password).encode()).hexdigest(), hashed
        )
    except (AttributeError, ValueError):
        return False


def generate_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


def token_required(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            g.current_user = jwt.decode(
                token, app.config['SECRET_KEY'], algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return function(*args, **kwargs)
    return decorated


def product_with_category(db, product):
    result = dict(product)
    category = db.categories.find_one({'id': product.get('category_id')})
    result['category_name'] = category['name'] if category else None
    result['category_slug'] = category['slug'] if category else None
    return result


def order_with_items(order):
    result = dict(order)
    result['items'] = result.get('items', [])
    return result


@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not name or not email or not password:
        return jsonify({'error': 'All fields required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    db = get_db()
    if db.users.find_one({'email': email}, {'_id': 1}):
        return jsonify({'error': 'Email already registered'}), 409
    user_id = next_id(db, 'users')
    user = {
        'id': user_id,
        'name': name,
        'email': email,
        'password_hash': hash_password(password),
        'role': 'customer',
        'created_at': datetime.datetime.utcnow(),
    }
    try:
        db.users.insert_one(user)
    except DuplicateKeyError:
        return jsonify({'error': 'Email already registered'}), 409
    token = generate_token(user_id, 'customer')
    return jsonify({
        'token': token,
        'user': {'id': user_id, 'name': name, 'email': email, 'role': 'customer'},
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    user = get_db().users.find_one({'email': email})
    if not user or not check_password(password, user.get('password_hash')):
        return jsonify({'error': 'Invalid email or password'}), 401
    token = generate_token(user['id'], user['role'])
    return jsonify({
        'token': token,
        'user': {
            'id': user['id'], 'name': user['name'],
            'email': user['email'], 'role': user['role'],
        },
    })


@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    user = get_db().users.find_one(
        {'id': g.current_user['user_id']},
        {'_id': 0, 'id': 1, 'name': 1, 'email': 1, 'role': 1, 'created_at': 1},
    )
    return jsonify(serialize(user)) if user else (jsonify({'error': 'User not found'}), 404)


@app.route('/api/products', methods=['GET'])
def get_products():
    db = get_db()
    category = request.args.get('category')
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'created_at')
    page = max(1, request.args.get('page', 1, type=int))
    limit = min(100, max(1, request.args.get('limit', 12, type=int)))
    query = {'stock': {'$gt': 0}}
    if category and category != 'all':
        category_doc = db.categories.find_one({'slug': category})
        query['category_id'] = category_doc['id'] if category_doc else -1
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'description': {'$regex': search, '$options': 'i'}},
        ]
    sort_fields = {
        'price_asc': ('price', ASCENDING),
        'price_desc': ('price', -1),
        'rating': ('rating', -1),
        'newest': ('created_at', -1),
    }
    sort_field, direction = sort_fields.get(sort, ('created_at', -1))
    total = db.products.count_documents(query)
    products = db.products.find(query).sort(sort_field, direction).skip((page - 1) * limit).limit(limit)
    return jsonify({
        'products': [serialize(product_with_category(db, product)) for product in products],
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit,
    })


@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    db = get_db()
    product = db.products.find_one({'id': product_id})
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    reviews = list(db.reviews.find({'product_id': product_id}).sort('created_at', -1).limit(10))
    for review in reviews:
        user = db.users.find_one({'id': review['user_id']}, {'name': 1})
        review['user_name'] = user.get('name') if user else None
    related = list(db.products.find({
        'category_id': product.get('category_id'),
        'id': {'$ne': product_id},
        'stock': {'$gt': 0},
    }).limit(4))
    return jsonify({
        'product': serialize(product_with_category(db, product)),
        'reviews': serialize(reviews),
        'related': serialize(related),
    })


@app.route('/api/categories', methods=['GET'])
def get_categories():
    db = get_db()
    categories = list(db.categories.find().sort('id', ASCENDING))
    for category in categories:
        category['product_count'] = db.products.count_documents({
            'category_id': category['id'], 'stock': {'$gt': 0},
        })
    return jsonify(serialize(categories))


@app.route('/api/orders', methods=['POST'])
@token_required
def create_order():
    data = request.get_json() or {}
    items = data.get('items', [])
    shipping = data.get('shipping', {})
    if not items:
        return jsonify({'error': 'Cart is empty'}), 400

    db = get_db()
    validated_items = []
    total = 0
    for item in items:
        try:
            product_id = int(item['product_id'])
            quantity = int(item['quantity'])
        except (KeyError, TypeError, ValueError):
            return jsonify({'error': 'Invalid cart item'}), 400
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be greater than zero'}), 400
        product = db.products.find_one({'id': product_id})
        if not product:
            return jsonify({'error': f'Product {product_id} not found'}), 404
        total += product['price'] * quantity
        validated_items.append((product, quantity))

    reserved = []
    for product, quantity in validated_items:
        updated = db.products.find_one_and_update(
            {'id': product['id'], 'stock': {'$gte': quantity}},
            {'$inc': {'stock': -quantity}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            for reserved_id, reserved_quantity in reserved:
                db.products.update_one(
                    {'id': reserved_id}, {'$inc': {'stock': reserved_quantity}}
                )
            return jsonify({'error': f'Insufficient stock for {product["name"]}'}), 400
        reserved.append((product['id'], quantity))

    order_id = next_id(db, 'orders')
    created_at = datetime.datetime.utcnow()
    order_items = [
        {
            'id': index,
            'order_id': order_id,
            'product_id': product['id'],
            'quantity': quantity,
            'price': product['price'],
            'name': product['name'],
            'image_url': product.get('image_url'),
        }
        for index, (product, quantity) in enumerate(validated_items, start=1)
    ]
    order = {
        'id': order_id,
        'user_id': g.current_user['user_id'],
        'total': round(total, 2),
        'status': 'processing',
        'shipping_name': shipping.get('name', ''),
        'shipping_address': shipping.get('address', ''),
        'shipping_city': shipping.get('city', ''),
        'shipping_zip': shipping.get('zip', ''),
        'payment_method': data.get('payment_method', 'card'),
        'created_at': created_at,
        'items': order_items,
    }
    try:
        db.orders.insert_one(order)
    except Exception:
        for reserved_id, reserved_quantity in reserved:
            db.products.update_one(
                {'id': reserved_id}, {'$inc': {'stock': reserved_quantity}}
            )
        raise
    return jsonify({'order_id': order_id, 'total': order['total'], 'status': 'processing'}), 201


@app.route('/api/orders', methods=['GET'])
@token_required
def get_orders():
    orders = get_db().orders.find(
        {'user_id': g.current_user['user_id']}
    ).sort('created_at', -1)
    return jsonify(serialize([order_with_items(order) for order in orders]))


@app.route('/api/orders/<int:order_id>', methods=['GET'])
@token_required
def get_order(order_id):
    order = get_db().orders.find_one({
        'id': order_id, 'user_id': g.current_user['user_id'],
    })
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    return jsonify(serialize(order_with_items(order)))


@app.route('/api/products/<int:product_id>/reviews', methods=['POST'])
@token_required
def add_review(product_id):
    data = request.get_json() or {}
    try:
        rating = int(data.get('rating', 0))
    except (TypeError, ValueError):
        rating = 0
    comment = data.get('comment', '').strip()
    if not 1 <= rating <= 5:
        return jsonify({'error': 'Rating must be 1-5'}), 400

    db = get_db()
    if not db.products.find_one({'id': product_id}, {'_id': 1}):
        return jsonify({'error': 'Product not found'}), 404
    review = {
        'id': next_id(db, 'reviews'),
        'product_id': product_id,
        'user_id': g.current_user['user_id'],
        'rating': rating,
        'comment': comment,
        'created_at': datetime.datetime.utcnow(),
    }
    try:
        db.reviews.insert_one(review)
    except DuplicateKeyError:
        return jsonify({'error': 'Already reviewed this product'}), 409
    stats = list(db.reviews.aggregate([
        {'$match': {'product_id': product_id}},
        {'$group': {'_id': None, 'average': {'$avg': '$rating'}, 'count': {'$sum': 1}}},
    ]))
    db.products.update_one({'id': product_id}, {'$set': {
        'rating': round(stats[0]['average'], 1),
        'review_count': stats[0]['count'],
    }})
    return jsonify({'message': 'Review added'}), 201


@app.route('/api/health')
def health():
    try:
        get_db().command('ping')
        return jsonify({'status': 'ok', 'database': 'connected',
                        'time': datetime.datetime.utcnow().isoformat()})
    except Exception:
        return jsonify({'status': 'error', 'database': 'disconnected'}), 503


if __name__ == '__main__':
    init_db()
    app.run()
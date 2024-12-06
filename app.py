from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re
from datetime import datetime
from flask_pymongo import PyMongo

# Load environment variables
load_dotenv()

# Add these lines after load_dotenv()
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Update MongoDB connection
app.config["MONGO_URI"] = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/shoe_store')
mongo = PyMongo(app)
db = mongo.db
products = db.products

# User Authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    # Get filter parameters
    current_filters = {
        'gender': request.args.get('gender'),
        'category': request.args.get('category'),
        'color': request.args.get('color'),
        'origin': request.args.get('origin'),
        'min_price': request.args.get('min_price'),
        'max_price': request.args.get('max_price')
    }

    # Build query based on filters
    query = {}
    if current_filters['gender']:
        query['gender'] = current_filters['gender']
    if current_filters['category']:
        query['category'] = current_filters['category']
    if current_filters['color']:
        query['color'] = {'$regex': current_filters['color'], '$options': 'i'}
    if current_filters['origin']:
        query['origin'] = {'$regex': current_filters['origin'], '$options': 'i'}
    
    # Handle price range
    if current_filters['min_price'] or current_filters['max_price']:
        price_query = {}
        if current_filters['min_price']:
            price_query['$gte'] = float(current_filters['min_price'])
        if current_filters['max_price']:
            price_query['$lte'] = float(current_filters['max_price'])
        if price_query:
            query['price'] = price_query

    # Fetch products from database
    products = list(db.products.find(query))
    
    # Convert ObjectId to string for JSON serialization
    for product in products:
        product['_id'] = str(product['_id'])

    # Add user information for the template
    user = None
    is_admin = False
    if 'user' in session:
        user = db.users.find_one({'_id': ObjectId(session['user'])})
        is_admin = session.get('role') == 'admin'

    return render_template('home.html', 
                         products=products, 
                         current_filters=current_filters,
                         user=user,
                         is_admin=is_admin)

@app.route('/init-db')
def init_db():
    try:
        # Clear existing products
        products.delete_many({})
        
        # Sample products
        sample_products = [
            {
                'name': 'Nike Air Max 270',
                'price': 159.99,
                'description': 'Maximum comfort with stylish design',
                'image_url': 'https://images.unsplash.com/photo-1542291026-7eec264c27ff',
                'gender': 'Unisex',
                'origin': 'USA',
                'brand': 'Nike',
                'sizes': ['US 7', 'US 8', 'US 9', 'US 10', 'US 11'],
                'colors': ['Black/Red', 'White/Blue', 'Gray/Volt'],
                'stock': 45,
                'rating': 4.8
            },
            {
                'name': 'Adidas Ultraboost',
                'price': 189.99,
                'description': 'Premium running shoes',
                'image_url': 'https://images.unsplash.com/photo-1608231387042-66d1773070a5',
                'gender': 'Men',
                'origin': 'Germany',
                'brand': 'Adidas',
                'sizes': ['US 8', 'US 9', 'US 10', 'US 11'],
                'colors': ['Black', 'White', 'Blue'],
                'stock': 30,
                'rating': 4.7
            }
        ]
        
        # Insert products and print result
        result = products.insert_many(sample_products)
        print(f"Inserted {len(result.inserted_ids)} products")
        
        return jsonify({
            'message': f'Database initialized with {len(result.inserted_ids)} products',
            'status': 'success'
        })
    except Exception as e:
        print(f"Error in init_db: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/check-db')
def check_db():
    try:
        count = products.count_documents({})
        all_products = list(products.find())
        return jsonify({
            'product_count': count,
            'products': [{
                'name': p['name'],
                'price': p['price'],
                'brand': p['brand']
            } for p in all_products]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cart')
def view_cart():
    try:
        cart_items = []
        subtotal = 0
        shipping = 10
        
        # Clean up invalid IDs from cart
        valid_cart = []
        for pid in session.get('cart', []):
            try:
                product = products.find_one({'_id': ObjectId(pid)})
                if product:
                    valid_cart.append(pid)
            except:
                continue
        
        session['cart'] = valid_cart
        session.modified = True
        
        # Process valid cart items
        for product_id in set(valid_cart):  # Use set to get unique IDs
            try:
                product = products.find_one({'_id': ObjectId(product_id)})
                if product:
                    quantity = valid_cart.count(product_id)
                    product_dict = {
                        '_id': str(product['_id']),
                        'name': product['name'],
                        'price': float(product['price']),
                        'image_url': product['image_url'],
                        'category': product['category'],
                        'quantity': quantity,
                        'total': float(product['price']) * quantity
                    }
                    cart_items.append(product_dict)
                    subtotal += product_dict['total']
            except Exception as e:
                print(f"Error processing product {product_id}: {str(e)}")
                continue

        tax = round(subtotal * 0.1, 2)
        total = subtotal + shipping + tax if cart_items else 0
        shipping = shipping if cart_items else 0
        
        return render_template('cart.html', 
                             cart_items=cart_items,
                             subtotal=subtotal,
                             shipping=shipping,
                             tax=tax,
                             total=total)
                             
    except Exception as e:
        print(f"Error in view_cart: {str(e)}")
        return render_template('cart.html', 
                             cart_items=[],
                             subtotal=0,
                             shipping=0,
                             tax=0,
                             total=0)

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        print(f"Attempting to add product with ID: {product_id}")
        
        # Initialize cart if it doesn't exist
        if 'cart' not in session:
            session['cart'] = []
            print("Created new cart in session")
        
        # Find the product first
        product = products.find_one({'_id': ObjectId(product_id)})
        print(f"Found product in database: {product}")
        
        if product:
            # Convert ObjectId to string before adding to session
            product_id_str = str(product['_id'])
            session['cart'].append(product_id_str)
            session.modified = True
            print(f"Updated cart contents: {session['cart']}")
            
            return jsonify({
                'success': True,
                'message': 'Product added to cart',
                'cart_count': len(session['cart'])
            })
        else:
            print(f"Product not found with ID: {product_id}")
            return jsonify({'success': False, 'message': 'Product not found'})
            
    except Exception as e:
        print(f"Error in add_to_cart: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/search')
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    min_price = float(request.args.get('min_price', 0))
    max_price = float(request.args.get('max_price', 1000000))
    sort = request.args.get('sort', 'name_asc')
    
    # Build the filter query
    filter_query = {}
    if query:
        filter_query['$or'] = [
            {'name': {'$regex': query, '$options': 'i'}},
            {'description': {'$regex': query, '$options': 'i'}}
        ]
    if category:
        filter_query['category'] = category
    
    filter_query['price'] = {'$gte': min_price, '$lte': max_price}
    
    # Determine sort order
    sort_options = {
        'price_asc': ('price', 1),
        'price_desc': ('price', -1),
        'name_asc': ('name', 1),
        'name_desc': ('name', -1)
    }
    sort_field, sort_order = sort_options.get(sort, ('name', 1))
    
    # Get all categories for filter dropdown
    categories = products.distinct('category')
    
    # Get filtered products
    filtered_products = list(products.find(filter_query).sort(sort_field, sort_order))
    
    # Convert ObjectId to string for JSON serialization
    for product in filtered_products:
        product['_id'] = str(product['_id'])
    
    return render_template('search.html',
                         products=filtered_products,
                         categories=categories,
                         query=query,
                         selected_category=category,
                         min_price=min_price,
                         max_price=max_price,
                         sort=sort)

@app.route('/api/cart/count')
def get_cart_count():
    # Replace this with your actual cart counting logic
    cart = session.get('cart', [])
    return jsonify({'count': len(cart)})

@app.route('/api/cart/update', methods=['POST'])
def update_cart():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        action = data.get('action')
        
        if 'cart' not in session:
            session['cart'] = []
        
        # Clean up invalid IDs from cart
        valid_cart = []
        for pid in session['cart']:
            try:
                if products.find_one({'_id': ObjectId(pid)}):
                    valid_cart.append(pid)
            except:
                continue
        
        session['cart'] = valid_cart
        
        try:
            # Verify product exists
            product = products.find_one({'_id': ObjectId(product_id)})
            if not product:
                return jsonify({'success': False, 'message': 'Product not found'})
            
            product_id_str = str(product['_id'])
            
            if action == 'increase':
                session['cart'].append(product_id_str)
            elif action == 'decrease':
                if product_id_str in session['cart']:
                    session['cart'].remove(product_id_str)
            elif action == 'remove':
                session['cart'] = [pid for pid in session['cart'] if pid != product_id_str]
            
            session.modified = True
            
            # Calculate new totals
            subtotal = 0
            item_quantity = session['cart'].count(product_id_str)
            
            for pid in session['cart']:
                try:
                    p = products.find_one({'_id': ObjectId(pid)})
                    if p:
                        subtotal += float(p['price'])
                except:
                    continue
            
            cart_count = len(session['cart'])
            shipping = 10 if cart_count > 0 else 0
            tax = round(subtotal * 0.1, 2)
            total = subtotal + shipping + tax
            item_total = float(product['price']) * item_quantity
            
            return jsonify({
                'success': True,
                'cart_count': cart_count,
                'item_quantity': item_quantity,
                'item_total': f"${item_total:.2f}",
                'subtotal': f"${subtotal:.2f}",
                'shipping': f"${shipping:.2f}",
                'tax': f"${tax:.2f}",
                'total': f"${total:.2f}"
            })
            
        except Exception as e:
            print(f"Error processing product {product_id}: {str(e)}")
            return jsonify({'success': False, 'message': 'Invalid product ID'}), 400
            
    except Exception as e:
        print(f"Error in update_cart: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    data = request.get_json()
    item_id = data.get('item_id')
    
    cart = session.get('cart', [])
    
    # Remove all instances of the item
    cart = [i for i in cart if i != item_id]
    
    session['cart'] = cart
    session.modified = True
    
    return jsonify({'success': True})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        if db.users.find_one({'email': email}):
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        db.users.insert_one({
            'email': email,
            'password': hashed_password,
            'created_at': datetime.utcnow()
        })
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user'] = str(user['_id'])
            session['email'] = user['email']
            session['role'] = user.get('role', 'user')  # Add role to session
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        
        flash('Invalid email or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET'])
@login_required
def profile():
    user = db.users.find_one({'_id': ObjectId(session['user'])})
    return render_template('profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = ObjectId(session['user'])
    
    # Update user data
    update_data = {
        'name': request.form.get('name'),
        'email': request.form.get('email'),
        'phone': request.form.get('phone'),
        'address': request.form.get('address')
    }
    
    db.users.update_one(
        {'_id': user_id},
        {'$set': update_data}
    )
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

# Admin middleware
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('home'))
            
        return f(*args, **kwargs)
    return decorated_function

# Admin Dashboard
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Get statistics
    total_products = products.count_documents({})
    total_users = db.users.count_documents({})
    total_orders = db.orders.count_documents({})
    
    # Get recent orders
    recent_orders = list(db.orders.find().sort('created_at', -1).limit(5))
    
    # Calculate total revenue
    revenue = sum(order.get('total', 0) for order in db.orders.find())
    
    return render_template('admin/dashboard.html',
                         total_products=total_products,
                         total_users=total_users,
                         total_orders=total_orders,
                         recent_orders=recent_orders,
                         revenue=revenue)

# Product Management
@app.route('/admin/products')
@admin_required
def admin_products():
    product_list = list(products.find())
    return render_template('admin/products.html', products=product_list)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        try:
            product_data = {
                'name': request.form['name'],
                'price': float(request.form['price']),
                'description': request.form['description'],
                'category': request.form['category'],
                'image_url': request.form['image_url'],
                'stock': int(request.form['stock']),
                'created_at': datetime.now()
            }
            products.insert_one(product_data)
            flash('Product added successfully!', 'success')
            return redirect(url_for('admin_products'))
        except Exception as e:
            flash(f'Error adding product: {str(e)}', 'error')
    
    return render_template('admin/product_form.html')

@app.route('/admin/products/edit/<product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = products.find_one({'_id': ObjectId(product_id)})
    
    if request.method == 'POST':
        try:
            updated_data = {
                'name': request.form['name'],
                'price': float(request.form['price']),
                'description': request.form['description'],
                'category': request.form['category'],
                'image_url': request.form['image_url'],
                'stock': int(request.form['stock'])
            }
            products.update_one({'_id': ObjectId(product_id)}, {'$set': updated_data})
            flash('Product updated successfully!', 'success')
            return redirect(url_for('admin_products'))
        except Exception as e:
            flash(f'Error updating product: {str(e)}', 'error')
    
    return render_template('admin/product_form.html', product=product)

@app.route('/admin/products/delete/<product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    try:
        products.delete_one({'_id': ObjectId(product_id)})
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'error')
    return redirect(url_for('admin_products'))

# Order Management
@app.route('/admin/orders')
@admin_required
def admin_orders():
    all_orders = list(db.orders.find().sort('created_at', -1))
    return render_template('admin/orders.html', orders=all_orders)

@app.route('/admin/orders/<order_id>')
@admin_required
def order_detail(order_id):
    order = db.orders.find_one({'_id': ObjectId(order_id)})
    return render_template('admin/order_detail.html', order=order)

# User Management
@app.route('/admin/users')
@admin_required
def admin_users():
    all_users = list(db.users.find())
    return render_template('admin/users.html', users=all_users)

@app.route('/admin/setup', methods=['GET'])
def setup_admin():
    """One-time setup route to create admin account"""
    if db.users.find_one({'role': 'admin'}):
        flash('Admin already exists', 'warning')
        return redirect(url_for('home'))
    
    hashed_password = generate_password_hash(ADMIN_PASSWORD)
    db.users.insert_one({
        'email': ADMIN_EMAIL,
        'password': hashed_password,
        'role': 'admin',
        'created_at': datetime.utcnow()
    })
    flash('Admin account created', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
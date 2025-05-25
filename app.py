from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_db():
    conn = sqlite3.connect('olx.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/debug/uploads')
def debug_uploads():
    upload_folder = app.config['UPLOAD_FOLDER']
    files = os.listdir(upload_folder) if os.path.exists(upload_folder) else []
    return render_template('debug_uploads.html', files=files)

@app.route('/')
def index():
    category = request.args.get('category', '')
    conn = get_db()
    if category:
        products = conn.execute('SELECT * FROM products WHERE sold = 0 AND category = ?', (category,)).fetchall()
    else:
        products = conn.execute('SELECT * FROM products WHERE sold = 0').fetchall()
    categories = conn.execute('SELECT DISTINCT category FROM products WHERE sold = 0').fetchall()
    conn.close()
    return render_template('index.html', products=products, categories=categories, selected_category=category)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists!')
        conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!')
            return redirect(url_for('index'))
        flash('Invalid credentials!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out successfully!')
    return redirect(url_for('index'))

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user_id' not in session:
        flash('Please login to sell products!')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        user_id = session['user_id']
        image_path = None
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f'uploads/{filename}'
                flash(f'Image uploaded: {image_path}')
        
        conn = get_db()
        conn.execute('INSERT INTO products (title, description, price, category, user_id, image_path) VALUES (?, ?, ?, ?, ?, ?)',
                     (title, description, price, category, user_id, image_path))
        conn.commit()
        conn.close()
        flash('Product listed successfully!')
        return redirect(url_for('index'))
    
    return render_template('sell.html')

@app.route('/product/<int:id>')
def product(id):
    conn = get_db()
    product = conn.execute('SELECT p.*, u.username FROM products p JOIN users u ON p.user_id = u.id WHERE p.id = ?', (id,)).fetchone()
    conn.close()
    return render_template('product.html', product=product)

@app.route('/buy/<int:id>', methods=['GET', 'POST'])
def buy(id):
    if 'user_id' not in session:
        flash('Please login to buy products!')
        return redirect(url_for('login'))
    
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        if product and product['sold'] == 0:
            # Simulate payment processing
            card_number = request.form.get('card_number')
            expiry = request.form.get('expiry')
            cvv = request.form.get('cvv')
            
            # Basic validation (for demo purposes)
            if card_number and len(card_number) >= 12 and expiry and cvv and len(cvv) >= 3:
                conn.execute('UPDATE products SET sold = 1, buyer_id = ? WHERE id = ?', (session['user_id'], id))
                conn.commit()
                flash('Mock payment successful! Product purchased.')
                conn.close()
                return redirect(url_for('index'))
            else:
                flash('Invalid payment details!')
                conn.close()
                return render_template('payment.html', product=product)
        flash('Product not available!')
        conn.close()
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('buy.html', product=product)

@app.route('/buy_cart', methods=['GET', 'POST'])
def buy_cart():
    if 'user_id' not in session:
        flash('Please login to buy products!')
        return redirect(url_for('login'))
    
    conn = get_db()
    cart_items = conn.execute('SELECT p.*, c.quantity FROM products p JOIN cart c ON p.id = c.product_id WHERE c.user_id = ?', (session['user_id'],)).fetchall()
    
    if not cart_items:
        flash('Your cart is empty!')
        conn.close()
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        card_number = request.form.get('card_number')
        expiry = request.form.get('expiry')
        cvv = request.form.get('cvv')
        
        if card_number and len(card_number) >= 12 and expiry and cvv and len(cvv) >= 3:
            for item in cart_items:
                if item['sold'] == 0:
                    conn.execute('UPDATE products SET sold = 1, buyer_id = ? WHERE id = ?', (session['user_id'], item['id']))
            conn.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
            conn.commit()
            flash('Mock payment successful! Cart purchased.')
            conn.close()
            return redirect(url_for('index'))
        else:
            flash('Invalid payment details!')
            conn.close()
            return render_template('payment_cart.html', cart_items=cart_items, total_price=sum(item['price'] * item['quantity'] for item in cart_items))
    
    conn.close()
    return render_template('payment_cart.html', cart_items=cart_items, total_price=sum(item['price'] * item['quantity'] for item in cart_items))

@app.route('/wishlist')
def wishlist():
    if 'user_id' not in session:
        flash('Please login to view wishlist!')
        return redirect(url_for('login'))
    
    conn = get_db()
    wishlist = conn.execute('SELECT p.* FROM products p JOIN wishlist w ON p.id = w.product_id WHERE w.user_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('wishlist.html', wishlist=wishlist)

@app.route('/add_to_wishlist/<int:id>')
def add_to_wishlist(id):
    if 'user_id' not in session:
        flash('Please login to add to wishlist!')
        return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)', (session['user_id'], id))
    conn.commit()
    conn.close()
    flash('Added to wishlist!')
    return redirect(url_for('product', id=id))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please login to view cart!')
        return redirect(url_for('login'))
    
    conn = get_db()
    cart_items = conn.execute('SELECT p.*, c.quantity FROM products p JOIN cart c ON p.id = c.product_id WHERE c.user_id = ?', (session['user_id'],)).fetchall()
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    conn.close()
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/add_to_cart/<int:id>', methods=['POST'])
def add_to_cart(id):
    if 'user_id' not in session:
        flash('Please login to add to cart!')
        return redirect(url_for('login'))
    
    quantity = int(request.form.get('quantity', 1))
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    
    if product and product['sold'] == 0:
        conn.execute('INSERT OR IGNORE INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)', 
                     (session['user_id'], id, quantity))
        conn.execute('UPDATE cart SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?', 
                     (quantity, session['user_id'], id))
        conn.commit()
        flash('Added to cart!')
    else:
        flash('Product not available!')
    conn.close()
    return redirect(url_for('product', id=id))

@app.route('/remove_from_cart/<int:id>')
def remove_from_cart(id):
    if 'user_id' not in session:
        flash('Please login to modify cart!')
        return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute('DELETE FROM cart WHERE user_id = ? AND product_id = ?', (session['user_id'], id))
    conn.commit()
    conn.close()
    flash('Removed from cart!')
    return redirect(url_for('cart'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        flash('Please login to view history!')
        return redirect(url_for('login'))
    
    conn = get_db()
    sold = conn.execute('SELECT * FROM products WHERE user_id = ? AND sold = 1', (session['user_id'],)).fetchall()
    bought = conn.execute('SELECT * FROM products WHERE buyer_id = ?', (session['user_id'],)).fetchall()
    searches = conn.execute('SELECT * FROM search_history WHERE user_id = ? ORDER BY timestamp DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('history.html', sold=sold, bought=bought, searches=searches)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    if query and 'user_id' in session:
        conn = get_db()
        conn.execute('INSERT INTO search_history (user_id, query, timestamp) VALUES (?, ?, ?)',
                     (session['user_id'], query, datetime.now()))
        conn.commit()
        products = conn.execute('SELECT * FROM products WHERE title LIKE ? AND sold = 0', (f'%{query}%',)).fetchall()
        categories = conn.execute('SELECT DISTINCT category FROM products WHERE sold = 0').fetchall()
        conn.close()
    else:
        conn = get_db()
        products = conn.execute('SELECT * FROM products WHERE sold = 0').fetchall()
        categories = conn.execute('SELECT DISTINCT category FROM products WHERE sold = 0').fetchall()
        conn.close()
    return render_template('index.html', products=products, query=query, categories=categories)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        category TEXT NOT NULL,
        user_id INTEGER,
        sold INTEGER DEFAULT 0,
        buyer_id INTEGER,
        image_path TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (buyer_id) REFERENCES users(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS wishlist (
        user_id INTEGER,
        product_id INTEGER,
        PRIMARY KEY (user_id, product_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS cart (
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, product_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        query TEXT NOT NULL,
        timestamp DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()
    app.run(debug=True)
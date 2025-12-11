# --- app.py ---

from locale import currency
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from config import Config
from datetime import datetime
from utils import export_to_csv, import_csv_to_list
import os 
import json 
from werkzeug.utils import secure_filename 
from werkzeug.security import generate_password_hash, check_password_hash 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user 

import qrcode 
from PIL import Image 
from io import BytesIO 
import base64 

# --- Application and Database Setup ---
app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 
db = SQLAlchemy(app)

# --- Configuration Helpers ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
CUSTOM_COLUMN_KEYS = ['supplier', 'location', 'color'] 

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Register filter for currency display (INR)
@app.template_filter('currency')
def format_currency(value):
    return f'₹ {value:,.2f}'

@app.template_filter('from_json')
def from_json_filter(json_data):
    """Converts a JSON string to a Python dictionary/list."""
    try:
        return json.loads(json_data)
    except (json.JSONDecodeError, TypeError):
        return {}

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Models ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_path = db.Column(db.String(255), nullable=True) 
    custom_data = db.Column(db.String(500), nullable=True) # Used for QR Code Base64 Data

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    transactions = db.relationship('Transaction', 
                                   backref='customer', 
                                   lazy=True,
                                   cascade="all, delete-orphan") 

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False) 
    total_cost = db.Column(db.Float, nullable=False) 
    status = db.Column(db.String(50), default='Cash') 
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True) 

# --- QR CODE GENERATION ---
def generate_product_qr(product_id):
    qr_data = f"POS_PRODUCT_{product_id}" 
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

@app.route('/download_qr/<int:product_id>')
@login_required
def download_qr(product_id):
    product = Product.query.get_or_404(product_id)
    qr_base64 = generate_product_qr(product.id)
    qr_bytes = base64.b64decode(qr_base64)
    buffer = BytesIO(qr_bytes)
    
    return send_file(
        buffer,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'QR_Code_{product.name}.png'
    )

# --- AUTHENTICATION ROUTES (SECURITY FIX APPLIED) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        # Check password against hash
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            # CRITICAL SECURITY FIX: Redirect immediately upon failure
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login')) 
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- CORE APPLICATION ROUTES ---

@app.route('/')
@login_required
def index():
    products = Product.query.all()
    customers = Customer.query.order_by(Customer.name).all() 
    return render_template('index.html', products=products, all_customers=customers)

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    data = request.get_json()
    cart_items = data.get('cart', [])
    customer_id = data.get('customer_id') or None
    payment_method = data.get('payment_method', 'Cash') 
    
    total_amount = 0.0
    total_cost = 0.0
    
    try:
        for item in cart_items:
            product = Product.query.get(item['id'])
            if product:
                qty = item['qty']
                subtotal = product.price * qty
                total_amount += subtotal
                total_cost += (product.price * 0.70) * qty
                
                if product.stock >= qty:
                    product.stock -= qty
                else:
                    db.session.rollback()
                    return jsonify({'success': False, 'message': f"Insufficient stock for {product.name}"}), 400

        new_transaction = Transaction(
            total_amount=total_amount,
            total_cost=total_cost,
            status=payment_method,
            customer_id=customer_id
        )
        
        db.session.add(new_transaction)
        db.session.commit()
        
        return jsonify({'success': True, 'transaction_id': new_transaction.id}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/receipt/<int:transaction_id>')
@login_required
def receipt(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    customer = Customer.query.get(transaction.customer_id) if transaction.customer_id else None
    
    placeholder_cart = [
        {'name': 'Dummy Item 1', 'qty': 1, 'price': 100.00, 'subtotal': 100.00},
        {'name': 'Dummy Item 2', 'qty': 2, 'price': 50.00, 'subtotal': 100.00},
    ]
    
    return render_template('receipt.html', transaction=transaction, customer=customer, cart=placeholder_cart)

# --- CUSTOMER MANAGEMENT ---

@app.route('/customers')
@login_required
def customers():
    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)

@app.route('/customer_form', methods=['GET'])
@app.route('/customer_form/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def customer_form(customer_id=None):
    if customer_id:
        customer = Customer.query.get_or_404(customer_id)
        title = f'Edit Customer: {customer.name}'
    else:
        customer = None
        title = 'Add New Customer'

    if request.method == 'POST':
        if customer is None:
            customer = Customer()
            
        try:
            customer.name = request.form.get('name')
            customer.phone = request.form.get('phone')
            customer.email = request.form.get('email')
            customer.address = request.form.get('address')
            
            if customer_id is None:
                db.session.add(customer)
                flash(f'Customer "{customer.name}" added successfully.', 'success')
            else:
                flash(f'Customer "{customer.name}" updated successfully.', 'success')

            db.session.commit()
            return redirect(url_for('customers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving customer: Phone or Email may already exist. ({e})', 'error')

    return render_template('customer_form.html', title=title, customer=customer)


@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    try:
        db.session.delete(customer)
        db.session.commit()
        flash(f'Customer "{customer.name}" and all their transaction history have been deleted.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {e}', 'error')

    return redirect(url_for('customers'))

@app.route('/add_customer_quick', methods=['POST'])
@login_required
def add_customer_quick():
    data = request.get_json()
    name = data.get('name')
    phone = data.get('phone')
    
    if not name or not phone:
        return jsonify({'success': False, 'message': 'Name and Phone are required.'}), 400
        
    try:
        new_customer = Customer(name=name, phone=phone)
        db.session.add(new_customer)
        db.session.commit()
        return jsonify({'success': True, 'customer_id': new_customer.id, 'name': new_customer.name, 'phone': new_customer.phone}), 200
        
    except Exception as e:
        db.session.rollback()
        error_msg = 'Phone number already registered.' if 'UNIQUE' in str(e) else str(e)
        return jsonify({'success': False, 'message': error_msg}), 400

@app.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    purchase_history = Transaction.query.filter_by(customer_id=customer_id).order_by(Transaction.timestamp.desc()).all()
    
    # Calculate outstanding credit dynamically (Credit sales - Payments received)
    total_credit_sales = sum(t.total_amount for t in purchase_history if t.status == 'Credit')
    total_payments_received = sum(abs(t.total_amount) for t in purchase_history if t.status == 'Payment')
    outstanding_credit = total_credit_sales - total_payments_received
    
    return render_template('customer_detail.html', 
                           customer=customer, 
                           history=purchase_history,
                           credit_due=outstanding_credit)

@app.route('/record_payment/<int:customer_id>', methods=['POST'])
@login_required
def record_payment(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    try:
        payment_amount = float(request.form.get('payment_amount', 0.0))
    except ValueError:
        flash('Invalid payment amount.', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))
    
    if payment_amount <= 0:
        flash('Payment amount must be greater than zero.', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))

    # Recalculate outstanding credit dynamically
    all_transactions = Transaction.query.filter_by(customer_id=customer_id).all()
    total_credit_sales = sum(t.total_amount for t in all_transactions if t.status == 'Credit')
    total_payments_received = sum(abs(t.total_amount) for t in all_transactions if t.status == 'Payment')
    outstanding_credit = total_credit_sales - total_payments_received
    
    if outstanding_credit <= 0:
        flash('Customer has no outstanding balance due.', 'info')
        return redirect(url_for('customer_detail', customer_id=customer_id))
        
    if payment_amount > outstanding_credit:
        flash(f'Payment amount ({payment_amount | currency}) exceeds the total due ({outstanding_credit | currency}).', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))


    # Record the Payment as a NEGATIVE Transaction
    try:
        payment_transaction = Transaction(
            total_amount=-payment_amount, # Negative value to represent money received
            total_cost=0.0,
            status='Payment', # Status for debt payment
            customer_id=customer_id,
            timestamp=datetime.utcnow()
        )
        db.session.add(payment_transaction)
        db.session.commit()
        
        flash(f'Payment of {payment_amount | currency} recorded successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {e}', 'error')
        
    return redirect(url_for('customer_detail', customer_id=customer_id))


# --- INVENTORY MANAGEMENT ---

@app.route('/products')
@login_required
def products():
    products = Product.query.all()
    custom_headers = ["supplier", "location", "color"] 
    return render_template('products.html', products=products, custom_headers=custom_headers)

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price', 0.0))
        stock = int(request.form.get('stock', 0))
        
        image_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_path = os.path.join('uploads', filename)
        
        custom_data_dict = {}
        for key in CUSTOM_COLUMN_KEYS:
            custom_data_dict[key] = request.form.get(f'custom_{key}', '')
        
        custom_data_json = json.dumps(custom_data_dict)

        try:
            new_product = Product(
                name=name, 
                price=price, 
                stock=stock, 
                image_path=image_path,
                custom_data=custom_data_json
            )
            db.session.add(new_product)
            db.session.commit()
            
            new_product.custom_data = generate_product_qr(new_product.id)
            db.session.commit()
            
            flash(f'Product "{name}" added successfully with QR code.', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {e}', 'error')
            
    return render_template('product_form.html', title='Add New Product', product=None, custom_keys=CUSTOM_COLUMN_KEYS)


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        try:
            product.name = request.form.get('name')
            product.price = float(request.form.get('price', 0.0))
            product.stock = int(request.form.get('stock', 0))

            if 'photo' in request.files:
                file = request.files['photo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    product.image_path = os.path.join('uploads', filename)
            
            custom_data_dict = {}
            for key in CUSTOM_COLUMN_KEYS:
                custom_data_dict[key] = request.form.get(f'custom_{key}', '')
            
            product.custom_data = json.dumps(custom_data_dict)
            
            db.session.commit()
            flash(f'Product "{product.name}" updated successfully.', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {e}', 'error')

    return render_template('product_form.html', title=f'Edit Product: {product.name}', product=product, custom_keys=CUSTOM_COLUMN_KEYS)


@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    try:
        db.session.delete(product)
        db.session.commit()
        flash(f'Product "{product.name}" deleted successfully.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: Cannot delete product with existing sales history. ({e})', 'error')

    return redirect(url_for('products'))

# --- ANALYSIS/SETTINGS/EXPORT ROUTES ---

@app.route('/analysis')
@login_required
def analysis():
    all_transactions = Transaction.query.all()
    all_products = Product.query.all()
    
    # --- Inventory Costing Calculation ---
    total_inventory_cost = 0.0
    for product in all_products:
        # Using 70% of sale price as estimated cost price
        estimated_cost_per_unit = product.price * 0.70
        total_inventory_cost += estimated_cost_per_unit * product.stock

    # --- Financial Metrics ---
    total_revenue = sum(t.total_amount for t in all_transactions if t.status != 'Void')
    total_cost_of_goods = sum(t.total_cost for t in all_transactions if t.status != 'Void')
    gross_profit = total_revenue - total_cost_of_goods
    
    # --- Sales & Debt Breakdown ---
    cash_sales = sum(t.total_amount for t in all_transactions if t.status == 'Cash')
    card_sales = sum(t.total_amount for t in all_transactions if t.status == 'Card')
    credit_sales = sum(t.total_amount for t in all_transactions if t.status == 'Credit')
    total_payments = sum(abs(t.total_amount) for t in all_transactions if t.status == 'Payment')
    
    total_credit_due = credit_sales - total_payments

    dead_stock_candidates = Product.query.filter(Product.stock > 10).limit(5).all() 
    business_loss_estimate = total_credit_due 

    return render_template('analysis.html', 
                           revenue=total_revenue,
                           profit=gross_profit,
                           cash_sales=cash_sales,
                           card_sales=card_sales,
                           total_credit_due=total_credit_due,
                           loss_estimate=business_loss_estimate,
                           total_inventory_cost=total_inventory_cost, 
                           dead_stock=dead_stock_candidates)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Admin password updated successfully.', 'success')
        
    return render_template('settings.html')

@app.route('/export/<model_name>')
@login_required
def export_data(model_name):
    if model_name == 'products':
        data = Product.query.all()
        return export_to_csv(data, 'inventory_export')
    elif model_name == 'customers':
        data = Customer.query.all()
        return export_to_csv(data, 'customers_export')
    
    flash('Invalid model specified for export.', 'error')
    return redirect(url_for('products'))

@app.route('/import/products', methods=['POST'])
@login_required
def import_products():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('products'))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('products'))
    
    if not file.filename.endswith('.csv'):
        flash('Invalid file format. Please upload a CSV file.', 'error')
        return redirect(url_for('products'))

    try:
        # 1. Read the CSV data using the helper function
        product_data_list = import_csv_to_list(file)
        
        products_added = 0
        products_updated = 0
        
        for row in product_data_list:
            # Clean and convert data types
            name = row.get('name', '').strip()
            price = float(row.get('price', 0.0))
            stock = int(row.get('stock', 0))
            
            # Use name as a unique identifier for updating existing products
            product = Product.query.filter_by(name=name).first()
            
            if product:
                # Update existing product
                product.price = price
                product.stock = product.stock + stock 
                products_updated += 1
            else:
                # Add new product
                new_product = Product(name=name, price=price, stock=stock)
                db.session.add(new_product)
                db.session.flush() 
                
                # Generate QR Code immediately
                new_product.custom_data = generate_product_qr(new_product.id)
                products_added += 1

        db.session.commit()
        flash(f'Import successful! Added {products_added} new products and updated stock for {products_updated} existing products.', 'success')
        
    except ValueError:
        db.session.rollback()
        flash('Import failed: Check CSV data types (Price and Stock must be numbers).', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Import failed due to an unexpected error: {e}', 'error')
        
    return redirect(url_for('products'))

# --- Initial Setup and Run ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not User.query.first():
            admin = User(username='admin')
            admin.set_password('adminpass')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: username='admin', password='adminpass'")
            
        if not Product.query.first():
            db.session.add_all([
                Customer(name='Karan', phone='9876543210', email='karan@example.com', address='123 '),
                Customer(name='Priya Sharma', phone='9988776655', email='priya@example.com', address='456 ')
            ])
            products_to_add = [
                Product(name='Red T-Shirt', price=250.00, stock=50),
                Product(name='Blue Jeans', price=1200.00, stock=30),
                Product(name='Leather Wallet', price=450.00, stock=10)
            ]
            db.session.add_all(products_to_add)
            db.session.commit()
            
            for product in Product.query.all():
                product.custom_data = generate_product_qr(product.id)
            db.session.commit()
            print("Dummy products created with QR codes generated.")
        
    app.run(debug=True, host='0.0.0.0')
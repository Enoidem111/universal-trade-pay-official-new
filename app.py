import os, sqlite3, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-before-production')
DB_PATH = os.environ.get('DATABASE_PATH', 'universal_trade_pay.db')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, account_type TEXT NOT NULL,
            full_name TEXT NOT NULL, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE,
            phone TEXT, country TEXT, address TEXT, company_name TEXT, password_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', role TEXT NOT NULL DEFAULT 'customer',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            asset TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
            UNIQUE(user_id, asset), FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL, asset TEXT NOT NULL, amount REAL NOT NULL,
            reference TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            message TEXT NOT NULL, created_at TEXT NOT NULL
        );
        ''')
        # Create an administrator only when credentials are supplied in the deployment environment.
        admin_email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        if admin_email and admin_password:
            exists = con.execute('SELECT id FROM users WHERE email=?', (admin_email,)).fetchone()
            if not exists:
                con.execute('''INSERT INTO users
                    (account_type,full_name,username,email,password_hash,status,role,created_at)
                    VALUES ('Corporate','Platform Administrator','admin',?,?, 'approved','admin',?)''',
                    (admin_email, generate_password_hash(admin_password), datetime.utcnow().isoformat()))

init_db()

@app.context_processor
def inject_globals():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(24)
    return {'csrf_token': session['csrf_token'], 'current_user': get_current_user()}


def get_current_user():
    uid = session.get('user_id')
    if not uid: return None
    with db() as con:
        return con.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()

@app.before_request
def csrf_protect():
    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        if not token or token != session.get('csrf_token'):
            abort(400, 'Your form session expired. Please go back, refresh, and try again.')


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            flash('Please sign in to continue.', 'warning'); return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped


def approved_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user['status'] != 'approved':
            return render_template('pending.html', user=user)
        return fn(*args, **kwargs)
    return wrapped


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if get_current_user()['role'] != 'admin': abort(403)
        return fn(*args, **kwargs)
    return wrapped

@app.route('/')
def home(): return render_template('home.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/payments')
def payments(): return render_template('payments.html')

@app.route('/features')
def features(): return render_template('features.html')

@app.route('/faq')
def faq(): return render_template('faq.html')

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you. Your message has been received in this demo. Connect an email service to enable delivery.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/privacy')
def privacy(): return render_template('legal.html', page_title='Privacy Policy')

@app.route('/terms')
def terms(): return render_template('legal.html', page_title='Terms & Conditions')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        account_type = request.form.get('account_type','Personal')
        full_name = request.form.get('full_name','').strip()
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        phone = request.form.get('phone','').strip()
        country = request.form.get('country','').strip()
        address = request.form.get('address','').strip()
        company_name = request.form.get('company_name','').strip()
        if account_type not in ('Personal','Corporate') or not all([full_name, username, email, password]):
            flash('Please complete all required fields.', 'danger')
        elif len(password) < 12:
            flash('Please use a password with at least 12 characters.', 'danger')
        else:
            try:
                with db() as con:
                    con.execute('''INSERT INTO users
                    (account_type,full_name,username,email,phone,country,address,company_name,password_hash,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,'pending',?)''',
                    (account_type,full_name,username,email,phone,country,address,company_name,
                     generate_password_hash(password),datetime.utcnow().isoformat()))
                flash('Your account request has been submitted. An administrator must approve it before dashboard access.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('That username or email is already registered.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        with db() as con: user = con.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.clear(); session['user_id'] = user['id']; session['csrf_token'] = secrets.token_urlsafe(24)
            return redirect(url_for('admin') if user['role']=='admin' else url_for('dashboard'))
        flash('Email or password is incorrect.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/dashboard')
@approved_required
def dashboard():
    user = get_current_user()
    with db() as con:
        balances = con.execute('SELECT asset,amount FROM balances WHERE user_id=? ORDER BY asset', (user['id'],)).fetchall()
        activity_rows = con.execute('SELECT * FROM activity WHERE user_id=? ORDER BY id DESC LIMIT 8', (user['id'],)).fetchall()
        transfers = con.execute('''SELECT t.*, u.email AS recipient_email FROM transfers t JOIN users u ON u.id=t.recipient_id
            WHERE t.sender_id=? OR t.recipient_id=? ORDER BY t.id DESC LIMIT 8''', (user['id'],user['id'])).fetchall()
    return render_template('dashboard.html', user=user, balances=balances, activity=activity_rows, transfers=transfers)

@app.route('/transfer', methods=['POST'])
@approved_required
def transfer():
    sender = get_current_user(); recipient_email=request.form.get('recipient_email','').strip().lower()
    asset=request.form.get('asset','USD').upper(); amount_raw=request.form.get('amount','0')
    try: amount=float(amount_raw)
    except ValueError: amount=0
    if asset not in ('USD','EUR','GBP','NGN','USDT') or amount <= 0:
        flash('Enter a valid amount and supported demo asset.', 'danger'); return redirect(url_for('dashboard'))
    with db() as con:
        recipient=con.execute("SELECT * FROM users WHERE email=? AND status='approved'", (recipient_email,)).fetchone()
        if not recipient: flash('No approved recipient account was found.', 'danger'); return redirect(url_for('dashboard'))
        if recipient['id']==sender['id']: flash('You cannot transfer to your own account.', 'danger'); return redirect(url_for('dashboard'))
        bal=con.execute('SELECT amount FROM balances WHERE user_id=? AND asset=?', (sender['id'],asset)).fetchone()
        if not bal or bal['amount'] < amount:
            flash('Insufficient demonstration balance. Ask the platform administrator to set a test balance.', 'danger'); return redirect(url_for('dashboard'))
        ref='UTP-'+secrets.token_hex(6).upper(); now=datetime.utcnow().isoformat()
        con.execute('UPDATE balances SET amount=amount-? WHERE user_id=? AND asset=?',(amount,sender['id'],asset))
        con.execute('INSERT INTO balances(user_id,asset,amount) VALUES(?,?,?) ON CONFLICT(user_id,asset) DO UPDATE SET amount=amount+excluded.amount',(recipient['id'],asset,amount))
        con.execute('INSERT INTO transfers(sender_id,recipient_id,asset,amount,reference,created_at) VALUES(?,?,?,?,?,?)',(sender['id'],recipient['id'],asset,amount,ref,now))
        con.execute('INSERT INTO activity(user_id,message,created_at) VALUES(?,?,?)',(sender['id'],f'Demo transfer of {amount:.2f} {asset} to {recipient_email} · {ref}',now))
        con.execute('INSERT INTO activity(user_id,message,created_at) VALUES(?,?,?)',(recipient['id'],f'Demo transfer received: {amount:.2f} {asset} · {ref}',now))
    flash(f'Demonstration transfer completed. Reference: {ref}. No real funds moved.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin')
@admin_required
def admin():
    with db() as con:
        users=con.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
        transfers=con.execute('''SELECT t.*,s.email sender_email,r.email recipient_email FROM transfers t
            JOIN users s ON s.id=t.sender_id JOIN users r ON r.id=t.recipient_id ORDER BY t.id DESC LIMIT 30''').fetchall()
    return render_template('admin.html', users=users, transfers=transfers)

@app.route('/admin/user/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_user(user_id):
    with db() as con:
        con.execute("UPDATE users SET status='approved' WHERE id=? AND role='customer'", (user_id,))
        con.execute('INSERT INTO activity(user_id,message,created_at) VALUES(?,?,?)',(user_id,'Your account has been approved.',datetime.utcnow().isoformat()))
    flash('Account approval updated.', 'success'); return redirect(url_for('admin'))

@app.route('/admin/balance', methods=['POST'])
@admin_required
def set_balance():
    try: user_id=int(request.form.get('user_id','0')); amount=float(request.form.get('amount','0'))
    except ValueError: user_id=0; amount=-1
    asset=request.form.get('asset','USD').upper()
    if amount < 0 or asset not in ('USD','EUR','GBP','NGN','USDT'):
        flash('Enter a valid demo balance.', 'danger'); return redirect(url_for('admin'))
    with db() as con:
        user=con.execute("SELECT id FROM users WHERE id=? AND role='customer'",(user_id,)).fetchone()
        if not user: flash('Customer account not found.', 'danger'); return redirect(url_for('admin'))
        con.execute('INSERT INTO balances(user_id,asset,amount) VALUES(?,?,?) ON CONFLICT(user_id,asset) DO UPDATE SET amount=excluded.amount',(user_id,asset,amount))
        con.execute('INSERT INTO activity(user_id,message,created_at) VALUES(?,?,?)',(user_id,f'Administrator updated your {asset} demonstration balance to {amount:.2f}.',datetime.utcnow().isoformat()))
    flash('Demonstration balance saved. This is not real money.', 'success'); return redirect(url_for('admin'))

@app.errorhandler(403)
def forbidden(e): return render_template('message.html', title='Access denied', message='You do not have permission to view this page.'),403

if __name__ == '__main__': app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=False)

from flask import Flask, render_template, request, redirect, url_for, flash, session, g, Response
import sqlite3
import os
import functools
import hashlib
import csv
import io
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bank.db')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'replace-with-a-secure-secret')


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def query_db(query, args=(), one=False):
    conn = get_db()
    cur = conn.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    def ensure_column(table, column, definition):
        cursor.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cursor.fetchall()]
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT,
            created_at TEXT NOT NULL
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            branch_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(branch_id) REFERENCES branches(id)
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            balance REAL NOT NULL CHECK(balance >= 0),
            customer_id INTEGER,
            branch_id INTEGER,
            account_type TEXT DEFAULT 'Savings',
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(branch_id) REFERENCES branches(id)
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            term_months INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            card_number TEXT NOT NULL UNIQUE,
            card_type TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            branch_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(branch_id) REFERENCES branches(id)
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            target_account INTEGER,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(id),
            FOREIGN KEY(target_account) REFERENCES accounts(id)
        )
        '''
    )

    ensure_column('users', 'role', "TEXT NOT NULL DEFAULT 'admin'")
    ensure_column('accounts', 'customer_id', 'INTEGER')
    ensure_column('accounts', 'branch_id', 'INTEGER')
    ensure_column('accounts', 'account_type', "TEXT DEFAULT 'Savings'")
    ensure_column('accounts', 'status', "TEXT DEFAULT 'Active'")
    ensure_column('customers', 'branch_id', 'INTEGER')
    ensure_column('employees', 'branch_id', 'INTEGER')
    ensure_column('transactions', 'target_account', 'INTEGER')

    conn.commit()
    conn.close()

    if not query_db('SELECT id FROM users WHERE email = ?', ('admin@bank.com',), one=True):
        execute_db(
            'INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
            ('Administrator', 'admin@bank.com', hash_password('admin123'), 'admin', now()),
        )

    if not query_db('SELECT id FROM branches ORDER BY id LIMIT 1', one=True):
        execute_db(
            'INSERT INTO branches (name, address, phone, created_at) VALUES (?, ?, ?, ?)',
            ('Downtown Branch', '123 Main Street', '+1 555 0100', now()),
        )

    if not query_db('SELECT id FROM customers ORDER BY id LIMIT 1', one=True):
        execute_db(
            'INSERT INTO customers (name, email, phone, branch_id, created_at) VALUES (?, ?, ?, ?, ?)',
            ('Default Customer', 'customer@bank.com', '+1 555 0200', 1, now()),
        )


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Please login to access the dashboard.', 'error')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = query_db('SELECT id, name, email, role FROM users WHERE id = ?', (user_id,), one=True)


def role_required(*accepted_roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None or g.user['role'] not in accepted_roles:
                flash('You do not have the required permissions to access that page.', 'error')
                return redirect(url_for('home'))
            return view(**kwargs)
        return wrapped_view
    return decorator


@app.context_processor
def inject_user():
    return dict(user=g.get('user'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = query_db('SELECT * FROM users WHERE email = ?', (email,), one=True)

        if user and user['password_hash'] == hash_password(password):
            session.clear()
            session['user_id'] = user['id']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('home'))

        flash('Incorrect email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def home():
    total_accounts = query_db('SELECT COUNT(*) AS count FROM accounts', one=True)['count']
    total_customers = query_db('SELECT COUNT(*) AS count FROM customers', one=True)['count']
    total_branches = query_db('SELECT COUNT(*) AS count FROM branches', one=True)['count']
    total_loans = query_db('SELECT COUNT(*) AS count FROM loans', one=True)['count']
    total_cards = query_db('SELECT COUNT(*) AS count FROM cards', one=True)['count']
    total_employees = query_db('SELECT COUNT(*) AS count FROM employees', one=True)['count']
    total_balance = query_db('SELECT COALESCE(SUM(balance), 0) AS sum FROM accounts', one=True)['sum']
    total_transactions = query_db('SELECT COUNT(*) AS count FROM transactions', one=True)['count']
    top_accounts = query_db(
        'SELECT a.*, c.name AS customer_name FROM accounts a LEFT JOIN customers c ON a.customer_id = c.id ORDER BY a.balance DESC LIMIT 3'
    )
    recent_transactions = [dict(txn) for txn in query_db(
        '''
        SELECT t.*, a.name AS account_name, b.name AS target_name
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts b ON t.target_account = b.id
        ORDER BY t.created_at DESC LIMIT 6
        '''
    )]
    for txn in recent_transactions:
        txn['note'] = txn['note'] or txn['type']
    return render_template(
        'home.html',
        total_accounts=total_accounts,
        total_customers=total_customers,
        total_branches=total_branches,
        total_loans=total_loans,
        total_cards=total_cards,
        total_employees=total_employees,
        total_balance=total_balance,
        total_transactions=total_transactions,
        top_accounts=top_accounts,
        recent_transactions=recent_transactions,
    )


@app.route('/branches')
@login_required
def list_branches():
    branches = query_db('SELECT * FROM branches ORDER BY id DESC')
    return render_template('branches.html', branches=branches)


@app.route('/branch/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_branch():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()

        if not name or not address:
            flash('Name and address are required.', 'error')
            return redirect(url_for('create_branch'))

        execute_db(
            'INSERT INTO branches (name, address, phone, created_at) VALUES (?, ?, ?, ?)',
            (name, address, phone, now()),
        )
        flash('Branch created successfully.', 'success')
        return redirect(url_for('list_branches'))

    return render_template('create_branch.html')


@app.route('/customers')
@login_required
def list_customers():
    search = request.args.get('query', '').strip()
    if search:
        pattern = f'%{search.lower()}%'
        customers = query_db(
            '''
            SELECT c.*, b.name AS branch_name
            FROM customers c
            LEFT JOIN branches b ON c.branch_id = b.id
            WHERE lower(c.name) LIKE ? OR lower(c.email) LIKE ?
            ORDER BY c.id DESC
            ''',
            (pattern, pattern),
        )
    else:
        customers = query_db('SELECT c.*, b.name AS branch_name FROM customers c LEFT JOIN branches b ON c.branch_id = b.id ORDER BY c.id DESC')
    branches = query_db('SELECT id, name FROM branches ORDER BY name ASC')
    return render_template('customers.html', customers=customers, search=search, branches=branches)


@app.route('/customer/new', methods=['GET', 'POST'])
@login_required
def create_customer():
    branches = query_db('SELECT id, name FROM branches ORDER BY name ASC')
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        branch_id = request.form.get('branch_id')

        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('create_customer'))

        existing = query_db('SELECT id FROM customers WHERE email = ?', (email,), one=True)
        if existing:
            flash('A customer with this email already exists.', 'error')
            return redirect(url_for('create_customer'))

        execute_db(
            'INSERT INTO customers (name, email, phone, branch_id, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, email, phone, branch_id or None, now()),
        )
        flash('Customer created successfully.', 'success')
        return redirect(url_for('list_customers'))

    return render_template('create_customer.html', branches=branches)


@app.route('/customer/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = query_db(
        '''
        SELECT c.*, b.name AS branch_name
        FROM customers c
        LEFT JOIN branches b ON c.branch_id = b.id
        WHERE c.id = ?
        ''',
        (customer_id,),
        one=True,
    )

    if customer is None:
        flash('Customer not found.', 'error')
        return redirect(url_for('list_customers'))

    customer_accounts = query_db('SELECT * FROM accounts WHERE customer_id = ? ORDER BY created_at DESC', (customer_id,))
    customer_loans = query_db(
        '''
        SELECT l.*, c.name AS customer_name, b.name AS branch_name
        FROM loans l
        LEFT JOIN customers c ON l.customer_id = c.id
        LEFT JOIN branches b ON c.branch_id = b.id
        WHERE l.customer_id = ?
        ORDER BY l.created_at DESC
        ''',
        (customer_id,),
    )

    return render_template('customer_detail.html', customer=customer, accounts=customer_accounts, loans=customer_loans)


@app.route('/reports')
@login_required
def reports():
    account_summary = query_db('SELECT COUNT(*) AS total_accounts, COALESCE(SUM(balance), 0) AS total_balance FROM accounts', one=True)
    loan_summary = query_db('SELECT COUNT(*) AS total_loans, COALESCE(SUM(amount), 0) AS total_loan_amount FROM loans', one=True)
    transaction_summary = query_db('SELECT COUNT(*) AS total_transactions, COALESCE(SUM(amount), 0) AS total_volume FROM transactions', one=True)
    return render_template('reports.html', account_summary=account_summary, loan_summary=loan_summary, transaction_summary=transaction_summary)


@app.route('/export/accounts')
@login_required
def export_accounts():
    rows = query_db(
        '''
        SELECT a.id, a.name, a.email, a.balance, c.name AS customer_name, b.name AS branch_name, a.account_type, a.status, a.created_at
        FROM accounts a
        LEFT JOIN customers c ON a.customer_id = c.id
        LEFT JOIN branches b ON a.branch_id = b.id
        ORDER BY a.id ASC
        '''
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Account ID', 'Name', 'Email', 'Balance', 'Customer', 'Branch', 'Type', 'Status', 'Created At'])
    for row in rows:
        writer.writerow([row['id'], row['name'], row['email'], row['balance'], row['customer_name'] or '', row['branch_name'] or '', row['account_type'], row['status'], row['created_at']])

    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=accounts_report.csv'})


@app.route('/export/transactions')
@login_required
def export_transactions():
    rows = query_db(
        '''
        SELECT t.id, t.created_at, a.name AS account_name, t.type, t.amount, b.name AS target_name, t.note
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts b ON t.target_account = b.id
        ORDER BY t.created_at DESC
        '''
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Transaction ID', 'Date', 'Account', 'Type', 'Amount', 'Target Account', 'Note'])
    for row in rows:
        writer.writerow([row['id'], row['created_at'], row['account_name'], row['type'], row['amount'], row['target_name'] or '', row['note'] or ''])

    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=transactions_report.csv'})


@app.route('/loan/<int:loan_id>/status', methods=['POST'])
@login_required
@role_required('admin')
def update_loan_status(loan_id):
    status = request.form.get('status', 'Pending').strip()
    if status not in ['Pending', 'Approved', 'Rejected']:
        flash('Invalid status selected.', 'error')
        return redirect(url_for('list_loans'))

    execute_db('UPDATE loans SET status = ? WHERE id = ?', (status, loan_id))
    flash('Loan status updated successfully.', 'success')
    return redirect(url_for('list_loans'))


@app.route('/card/<int:card_id>/status', methods=['POST'])
@login_required
@role_required('admin')
def update_card_status(card_id):
    status = request.form.get('status', 'Active').strip()
    if status not in ['Active', 'Suspended', 'Blocked']:
        flash('Invalid card status selected.', 'error')
        return redirect(url_for('list_cards'))

    execute_db('UPDATE cards SET status = ? WHERE id = ?', (status, card_id))
    flash('Card status updated successfully.', 'success')
    return redirect(url_for('list_cards'))


@app.route('/accounts')
@login_required
def list_accounts():
    search = request.args.get('query', '').strip()
    if search:
        pattern = f'%{search.lower()}%'
        accounts = query_db(
            '''
            SELECT a.*, c.name AS customer_name, b.name AS branch_name
            FROM accounts a
            LEFT JOIN customers c ON a.customer_id = c.id
            LEFT JOIN branches b ON a.branch_id = b.id
            WHERE lower(a.name) LIKE ? OR lower(a.email) LIKE ?
            ORDER BY a.id DESC
            ''',
            (pattern, pattern),
        )
    else:
        accounts = query_db(
            '''
            SELECT a.*, c.name AS customer_name, b.name AS branch_name
            FROM accounts a
            LEFT JOIN customers c ON a.customer_id = c.id
            LEFT JOIN branches b ON a.branch_id = b.id
            ORDER BY a.id DESC
            '''
        )
    return render_template('accounts.html', accounts=accounts, search=search)


@app.route('/account/new', methods=['GET', 'POST'])
@login_required
def create_account():
    customers = query_db('SELECT id, name FROM customers ORDER BY name ASC')
    branches = query_db('SELECT id, name FROM branches ORDER BY name ASC')

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        customer_id = request.form.get('customer_id')
        branch_id = request.form.get('branch_id')
        account_type = request.form.get('account_type', 'Savings').strip()
        status = request.form.get('status', 'Active').strip()
        balance = request.form.get('balance', '0').strip()

        if not name or not email or not customer_id or not branch_id:
            flash('Name, email, customer and branch are required.', 'error')
            return redirect(url_for('create_account'))

        if query_db('SELECT id FROM accounts WHERE email = ?', (email,), one=True):
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('create_account'))

        try:
            balance = float(balance)
        except ValueError:
            flash('Opening balance must be a valid number.', 'error')
            return redirect(url_for('create_account'))

        execute_db(
            'INSERT INTO accounts (name, email, balance, customer_id, branch_id, account_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (name, email, balance, customer_id, branch_id, account_type, status, now()),
        )
        flash('Account created successfully.', 'success')
        return redirect(url_for('list_accounts'))

    return render_template('create_account.html', customers=customers, branches=branches)


@app.route('/account/<int:account_id>')
@login_required
def account_details(account_id):
    account = query_db(
        '''
        SELECT a.*, c.name AS customer_name, b.name AS branch_name
        FROM accounts a
        LEFT JOIN customers c ON a.customer_id = c.id
        LEFT JOIN branches b ON a.branch_id = b.id
        WHERE a.id = ?
        ''',
        (account_id,),
        one=True,
    )

    if account is None:
        flash('Account not found.', 'error')
        return redirect(url_for('list_accounts'))

    transactions = query_db('SELECT * FROM transactions WHERE account_id = ? ORDER BY created_at DESC LIMIT 6', (account_id,))
    cards = query_db('SELECT * FROM cards WHERE account_id = ? ORDER BY created_at DESC', (account_id,))
    return render_template('account_detail.html', account=account, transactions=transactions, cards=cards)


@app.route('/transaction/<int:account_id>', methods=['GET', 'POST'])
@login_required
def transaction(account_id):
    action = request.args.get('action', 'deposit').lower()
    action_title = 'Deposit' if action == 'deposit' else 'Withdraw'
    account = query_db('SELECT * FROM accounts WHERE id = ?', (account_id,), one=True)

    if account is None:
        flash('Account not found.', 'error')
        return redirect(url_for('list_accounts'))

    if request.method == 'POST':
        amount = request.form.get('amount', '0').strip()
        note = request.form.get('note', '').strip()

        try:
            amount = float(amount)
        except ValueError:
            flash('Amount must be a valid number.', 'error')
            return redirect(url_for('transaction', account_id=account_id, action=action))

        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
            return redirect(url_for('transaction', account_id=account_id, action=action))

        if action == 'withdraw' and account['balance'] < amount:
            flash('Insufficient funds for withdrawal.', 'error')
            return redirect(url_for('transaction', account_id=account_id, action=action))

        new_balance = account['balance'] + amount if action == 'deposit' else account['balance'] - amount
        execute_db('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, account_id))
        execute_db(
            'INSERT INTO transactions (account_id, type, amount, note, created_at) VALUES (?, ?, ?, ?, ?)',
            (account_id, action_title, amount, note, now()),
        )
        flash(f'{action_title} completed successfully.', 'success')
        return redirect(url_for('account_details', account_id=account_id))

    return render_template('transaction.html', account=account, action_title=action_title)


@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    accounts = query_db('SELECT id, name, email, balance FROM accounts ORDER BY name ASC')

    if request.method == 'POST':
        source_account = request.form.get('source_account')
        target_account = request.form.get('target_account')
        amount = request.form.get('amount', '0').strip()
        note = request.form.get('note', '').strip()

        if not source_account or not target_account:
            flash('Please select both source and target accounts.', 'error')
            return redirect(url_for('transfer'))

        if source_account == target_account:
            flash('Source and target accounts must be different.', 'error')
            return redirect(url_for('transfer'))

        try:
            amount = float(amount)
        except ValueError:
            flash('Amount must be a valid number.', 'error')
            return redirect(url_for('transfer'))

        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
            return redirect(url_for('transfer'))

        source = query_db('SELECT * FROM accounts WHERE id = ?', (source_account,), one=True)
        target = query_db('SELECT * FROM accounts WHERE id = ?', (target_account,), one=True)

        if source is None or target is None:
            flash('Selected account not found.', 'error')
            return redirect(url_for('transfer'))

        if source['balance'] < amount:
            flash('Insufficient balance for transfer.', 'error')
            return redirect(url_for('transfer'))

        execute_db('UPDATE accounts SET balance = ? WHERE id = ?', (source['balance'] - amount, source_account))
        execute_db('UPDATE accounts SET balance = ? WHERE id = ?', (target['balance'] + amount, target_account))
        execute_db(
            'INSERT INTO transactions (account_id, type, amount, target_account, note, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (source_account, 'Transfer Out', amount, target_account, note or f'Transfer to {target["name"]}', now()),
        )
        execute_db(
            'INSERT INTO transactions (account_id, type, amount, target_account, note, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (target_account, 'Transfer In', amount, source_account, note or f'Transfer from {source["name"]}', now()),
        )

        flash('Transfer completed successfully.', 'success')
        return redirect(url_for('transactions'))

    return render_template('transfer.html', accounts=accounts)


@app.route('/employees')
@login_required
def list_employees():
    search = request.args.get('query', '').strip()
    if search:
        pattern = f'%{search.lower()}%'
        employees = query_db(
            '''
            SELECT e.*, b.name AS branch_name
            FROM employees e
            LEFT JOIN branches b ON e.branch_id = b.id
            WHERE lower(e.name) LIKE ? OR lower(e.email) LIKE ? OR lower(e.role) LIKE ?
            ORDER BY e.id DESC
            ''',
            (pattern, pattern, pattern),
        )
    else:
        employees = query_db('SELECT e.*, b.name AS branch_name FROM employees e LEFT JOIN branches b ON e.branch_id = b.id ORDER BY e.id DESC')
    branches = query_db('SELECT id, name FROM branches ORDER BY name ASC')
    return render_template('employees.html', employees=employees, search=search, branches=branches)


@app.route('/employee/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_employee():
    branches = query_db('SELECT id, name FROM branches ORDER BY name ASC')
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '').strip()
        branch_id = request.form.get('branch_id')

        if not name or not email or not role:
            flash('Name, email, and role are required.', 'error')
            return redirect(url_for('create_employee'))

        existing = query_db('SELECT id FROM employees WHERE email = ?', (email,), one=True)
        if existing:
            flash('An employee with this email already exists.', 'error')
            return redirect(url_for('create_employee'))

        execute_db(
            'INSERT INTO employees (name, email, role, branch_id, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, email, role, branch_id or None, now()),
        )
        flash('Employee created successfully.', 'success')
        return redirect(url_for('list_employees'))

    return render_template('create_employee.html', branches=branches)


@app.route('/loans')
@login_required
def list_loans():
    loans = query_db(
        '''
        SELECT l.*, c.name AS customer_name
        FROM loans l
        LEFT JOIN customers c ON l.customer_id = c.id
        ORDER BY l.id DESC
        '''
    )
    customers = query_db('SELECT id, name FROM customers ORDER BY name ASC')
    return render_template('loans.html', loans=loans, customers=customers)


@app.route('/loan/new', methods=['GET', 'POST'])
@login_required
def create_loan():
    customers = query_db('SELECT id, name FROM customers ORDER BY name ASC')
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        amount = request.form.get('amount', '0').strip()
        interest_rate = request.form.get('interest_rate', '0').strip()
        term_months = request.form.get('term_months', '0').strip()
        status = request.form.get('status', 'Pending').strip()

        if not customer_id or not amount or not interest_rate or not term_months:
            flash('All fields are required.', 'error')
            return redirect(url_for('create_loan'))

        try:
            amount = float(amount)
            interest_rate = float(interest_rate)
            term_months = int(term_months)
        except ValueError:
            flash('Amount, interest rate and term must be valid numbers.', 'error')
            return redirect(url_for('create_loan'))

        execute_db(
            'INSERT INTO loans (customer_id, amount, interest_rate, term_months, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (customer_id, amount, interest_rate, term_months, status, now()),
        )
        flash('Loan application created successfully.', 'success')
        return redirect(url_for('list_loans'))

    return render_template('create_loan.html', customers=customers)


@app.route('/cards')
@login_required
def list_cards():
    cards = query_db(
        '''
        SELECT c.*, a.name AS account_name
        FROM cards c
        JOIN accounts a ON c.account_id = a.id
        ORDER BY c.id DESC
        '''
    )
    accounts = query_db('SELECT id, name FROM accounts ORDER BY name ASC')
    return render_template('cards.html', cards=cards, accounts=accounts)


@app.route('/card/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_card():
    accounts = query_db('SELECT id, name FROM accounts ORDER BY name ASC')
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        card_type = request.form.get('card_type', 'Debit').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        status = request.form.get('status', 'Active').strip()

        if not account_id or not expiry_date:
            flash('Account and expiry date are required.', 'error')
            return redirect(url_for('create_card'))

        card_number = f'CARD{int(datetime.utcnow().timestamp())}{account_id}'.zfill(16)
        execute_db(
            'INSERT INTO cards (account_id, card_number, card_type, expiry_date, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (account_id, card_number, card_type, expiry_date, status, now()),
        )
        flash('Card issued successfully.', 'success')
        return redirect(url_for('list_cards'))

    return render_template('create_card.html', accounts=accounts)


@app.route('/transactions')
@login_required
def transactions():
    account_filter = request.args.get('account_id', '').strip()
    type_filter = request.args.get('type', '').strip()
    filters = []
    params = []

    if account_filter:
        filters.append('t.account_id = ?')
        params.append(account_filter)

    if type_filter:
        filters.append('t.type = ?')
        params.append(type_filter)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ''
    transactions = query_db(
        f'''
        SELECT t.*, a.name AS account_name, b.name AS target_name
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts b ON t.target_account = b.id
        {where_clause}
        ORDER BY t.created_at DESC
        ''',
        tuple(params),
    )
    accounts = query_db('SELECT id, name FROM accounts ORDER BY name ASC')
    return render_template('transactions.html', transactions=transactions, accounts=accounts, account_filter=account_filter, type_filter=type_filter)


@app.route('/users')
@login_required
@role_required('admin')
def list_users():
    search = request.args.get('query', '').strip()
    if search:
        pattern = f'%{search.lower()}%'
        users = query_db(
            'SELECT id, name, email, role, created_at FROM users WHERE lower(name) LIKE ? OR lower(email) LIKE ? ORDER BY id DESC',
            (pattern, pattern),
        )
    else:
        users = query_db('SELECT id, name, email, role, created_at FROM users ORDER BY id DESC')
    return render_template('users.html', users=users, search=search)


@app.route('/user/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_user():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'staff').strip()

        if not name or not email or not password:
            flash('Name, email, and password are required.', 'error')
            return redirect(url_for('create_user'))

        if role not in ['admin', 'manager', 'staff']:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('create_user'))

        if query_db('SELECT id FROM users WHERE email = ?', (email,), one=True):
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('create_user'))

        execute_db(
            'INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, email, hash_password(password), role, now()),
        )
        flash(f'User {name} created successfully as {role}.', 'success')
        return redirect(url_for('list_users'))

    return render_template('create_user.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)

# Smart Banking System

A full-stack Flask banking application with authentication, responsive UI, and SQLite persistence.

## Features

- Secure login page with session-based authentication
- Role-based access control: Admin, Manager, Staff
- Default admin user: `admin@bank.com` / `admin123`
- **Account management**: Create, view, and manage customer accounts
- **Deposits & withdrawals**: Process fund transactions with balance tracking
- **Money transfers**: Transfer funds between accounts with dual transaction logging
- **Customer profiles**: Detailed customer view with branch assignment
- **Loan management**: Create loan applications, track status (Pending/Approved/Rejected)
- **Card issuance**: Issue debit and credit cards with status control
- **Employee management**: Manage staff and assign to branches
- **Branch management**: Create and maintain service locations
- **Reporting & exports**: Dashboard overview with CSV export for accounts and transactions
- **Transaction history**: Filter and review all account activity
- **Staff administration**: Create admin, manager, and staff user accounts (admin-only)
- **Search & filter**: Find accounts, customers, transactions by name, email, or type
- **Responsive frontend**: Modern dark theme with SVG backgrounds

## Project Structure

- `app.py` — Flask backend, authentication, business logic, and database initialization
- `bank.db` — SQLite database file created automatically on first run
- `requirements.txt` — Python dependencies
- `templates/` — Jinja templates for pages
- `static/css/style.css` — frontend styling
- `static/img/` — decorative SVG background assets

## Setup

1. Create a Python virtual environment (recommended):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the application:

```powershell
python app.py
```

4. Open the app in your browser:

```text
http://127.0.0.1:5000
```

## Login

Use the built-in admin account to sign in:

- Email: `admin@bank.com`
- Password: `admin123`

## Database schema & initialization

- A SQL schema is available at `db/schema.sql`.
- To initialize or reset the SQLite database from the application, run the included script:

```powershell
python scripts\init_db.py
```

This will create `bank.db` (if missing) and ensure required tables and minimal default records exist. To seed sample customers and accounts, run:

```powershell
python scripts\seed_random.py
```

## ER Diagram

The database ER diagram source is available at [db/relationships.mmd](db/relationships.mmd).

To render a PNG (requires Node.js and Mermaid CLI) you can run:

```powershell
npx @mermaid-js/mermaid-cli -i db/relationships.mmd -o db/relationships.png
```

Or with the Mermaid CLI installed globally:

```powershell
mmdc -i db/relationships.mmd -o db/relationships.png
```

If you want, I can add the generated PNG to the repo for you — shall I create `db/relationships.png` now?

## Next update

- Add notification system for loan approvals and transaction alerts
- Implement scheduled loan payments and interest calculations
- Add advanced analytics dashboard with charts and trends
- Build mobile app or responsive PWA for on-the-go banking
- Implement API rate limiting and security hardening
- Add audit logging for compliance and fraud detection

## Notes

- `bank.db` is created automatically when the app is first run.
- To reset data, stop the app and delete `bank.db`.
- Replace `FLASK_SECRET_KEY` in your environment for production use.

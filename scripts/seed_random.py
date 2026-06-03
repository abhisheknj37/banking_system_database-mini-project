import os
import sys
import random
import uuid
from datetime import datetime

# ensure project root is on sys.path so `from app import ...` works when run from scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import init_db, execute_db, query_db, now


def random_phone():
    return f'+1 555 {random.randint(1000,9999):04d}'


def random_name(i):
    first = ['Alex', 'Sam', 'Jamie', 'Taylor', 'Jordan', 'Casey', 'Morgan', 'Riley', 'Cameron', 'Drew']
    last = ['Smith', 'Johnson', 'Brown', 'Williams', 'Jones', 'Miller', 'Davis', 'Garcia', 'Wilson', 'Taylor']
    return f"{random.choice(first)} {random.choice(last)} {i}"


def seed(n=50):
    init_db()

    branches = query_db('SELECT id FROM branches')
    branch_ids = [b['id'] for b in branches] or [1]

    created_customers = 0
    created_accounts = 0

    for i in range(n):
        name = random_name(i)
        unique = uuid.uuid4().hex[:8]
        email = f'{name.replace(" ","").lower()}.{unique}@example.com'
        phone = random_phone()
        branch_id = random.choice(branch_ids)

        try:
            customer_id = execute_db(
                'INSERT INTO customers (name, email, phone, branch_id, created_at) VALUES (?, ?, ?, ?, ?)',
                (name, email, phone, branch_id, now()),
            )
            created_customers += 1
        except Exception:
            # skip if unique constraint fails
            continue

        # create an account for this customer
        acct_email = f'{email}'
        balance = round(random.uniform(0, 10000), 2)
        account_type = random.choice(['Savings', 'Checking'])
        status = random.choice(['Active', 'Inactive'])

        try:
            execute_db(
                'INSERT INTO accounts (name, email, balance, customer_id, branch_id, account_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (name, acct_email, balance, customer_id, branch_id, account_type, status, now()),
            )
            created_accounts += 1
        except Exception:
            # skip accounts that violate constraints
            continue

    print(f'Created {created_customers} customers and {created_accounts} accounts.')


if __name__ == '__main__':
    seed(50)

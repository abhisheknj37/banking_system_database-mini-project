import os
import sys

# ensure project root is on sys.path so `from app import init_db` works when run from scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import init_db

if __name__ == '__main__':
    print('Initializing database...')
    init_db()
    print('Database initialized (bank.db).')
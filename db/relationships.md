# Database Relationships

This document describes the main entities and their relationships for the Smart Banking System SQLite schema.

Entities and relationships

- `users` — system users (admin/manager/staff).
  - Primary key: `id`.
  - Note: `users` are not currently linked to other tables by foreign keys in this schema.

- `branches` — bank branches.
  - Primary key: `id`.
  - One branch has many `customers`, `accounts`, and `employees`.

- `customers` — bank customers.
  - Primary key: `id`.
  - Foreign key: `branch_id` -> `branches(id)` (optional).
  - One customer can have many `accounts` and many `loans`.

- `accounts` — customer accounts.
  - Primary key: `id`.
  - Foreign keys: `customer_id` -> `customers(id)`, `branch_id` -> `branches(id)` (both optional in migration but used logically).
  - One account can have many `cards` and many `transactions` (as source and as target).

- `loans` — loan applications for customers.
  - Primary key: `id`.
  - Foreign key: `customer_id` -> `customers(id)`.

- `cards` — debit/credit cards tied to accounts.
  - Primary key: `id`.
  - Foreign key: `account_id` -> `accounts(id)`.

- `employees` — bank employees.
  - Primary key: `id`.
  - Foreign key: `branch_id` -> `branches(id)` (optional).

- `transactions` — account transactions.
  - Primary key: `id`.
  - Foreign keys: `account_id` -> `accounts(id)` (source), `target_account` -> `accounts(id)` (destination, nullable for non-transfers).

Cardinality summary

- Branch 1 —— * Customers
- Branch 1 —— * Accounts
- Branch 1 —— * Employees
- Customer 1 —— * Accounts
- Customer 1 —— * Loans
- Account 1 —— * Cards
- Account 1 —— * Transactions (as source)
- Account 1 —— * Transactions (as target)

Notes

- Important constraints: `accounts.email`, `customers.email`, `users.email`, `cards.card_number`, and `employees.email` are unique.
- `accounts.balance` has a CHECK to prevent negative balances.
- `transactions.target_account` is nullable to support deposits/withdrawals.
- The schema is in `db/schema.sql` and is kept in sync by `app.init_db()`.

If you'd like, I can generate a PNG of the ER diagram or add textual adjacency lists for each table.
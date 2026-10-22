# Supabase setup

This Flask application now uses Supabase exclusively through its HTTPS Data API.
It does not open a PostgreSQL, MySQL, or other SQL connection. It keeps the
existing Flask session, role checks, and password hashing; Supabase Auth is not
enabled by this migration.

## 1. Create the schema

Open the project's **SQL Editor** in the Supabase Dashboard and run both files
in order: `supabase/migrations/001_initial_schema.sql`, then
`supabase/migrations/002_api_rpcs.sql`. They create the tables, stock-related
constraints and indexes, plus the transactional RPC endpoints used by Flask.

The migration enables Row Level Security and removes browser Data API access to
these tables. That is intentional: this server is the trusted application
backend and connects with a private database connection string. Do not create
permissive `anon` policies just to make the publishable key work.

## 2. Configure the server

In the Supabase Dashboard, open **Settings > API** and copy the private
`sb_secret_...` key. This key remains on the Flask server and authorizes its
protected Data API and RPC calls.

Copy `.env.example` to `.env`, then set:

```dotenv
FLASK_SECRET_KEY=a-long-random-value
SUPABASE_URL=https://uamcxjuunivhfvkjurka.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

`SUPABASE_SECRET_KEY` is server-only, ignored by Git, and must never be placed
in `login.html`, JavaScript, or a Vite build.

The supplied `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` are safe
for a future browser Supabase client, but this server-rendered Flask app does
not use them for database administration. A publishable key is constrained by
Row Level Security and cannot safely replace the server credential.

## 3. Install and run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The initial self-signup role remains `Staff`. After the first account is
created, promote the intended administrator from the Supabase SQL Editor:

```sql
update public.users
set role = 'Admin'
where lower(email) = lower('admin@example.com');
```

## Existing MySQL data

The schema migration creates an empty Supabase database. If the previous MySQL
database has real records to preserve, export its tables and import them in
dependency order: `users`, `borrowers`, `equipment`, `borrowings`,
`borrowing_items`, `return_records`, then `audit_logs`. Preserve the existing
primary-key values while importing so the foreign keys stay valid.

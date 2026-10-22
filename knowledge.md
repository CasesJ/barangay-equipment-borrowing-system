# Barangay Equipment Borrowing System - Knowledge Base

## Purpose

This application manages barangay-owned reusable equipment and the full borrowing lifecycle: inventory, borrower records, requests, releases, returns, reports, and accountability logging. It is a server-rendered Flask application backed by MySQL.

## Quick start

1. Install dependencies: `pip install -r requirements.txt`.
2. Ensure MySQL is running and create/configure the `barangay_equipment_db` database with the tables listed below.
3. Set configuration through environment variables when needed:
   - `FLASK_SECRET_KEY`
   - `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
4. Start the application: `python app.py`.
5. Open `http://127.0.0.1:5000`.

Default connection values are `127.0.0.1:3306`, database `barangay_equipment_db`, user `root`, and an empty password. Replace the default Flask secret before deployment.

## Roles and permissions

| Role | Can do |
| --- | --- |
| Admin | Manage equipment and borrowers; create direct loans; review, approve, reject, cancel, and release user requests; record returns; view reports and audit logs. |
| User | Register an account, sign in, view available equipment, submit requests, monitor their own requests and borrowed items, and view their profile. |

New signups receive the `User` role and an associated borrower record. Protected pages use session-based authentication; protected API routes return JSON `401`/`403` errors where appropriate.

## Core workflow

```text
User request: Pending -> Approved -> Active -> Partially Returned -> Returned
                                -> Rejected / Cancelled

Admin direct loan: Active -> Partially Returned -> Returned
```

1. A User selects available equipment and supplies quantity, purpose, needed date, and expected return date.
2. The system creates a `Pending` borrowing request and reserves capacity against other pending/approved requests. Inventory stock is not reduced yet.
3. An Admin reviews the request. Approval changes it to `Approved`; rejection or cancellation ends the request without changing stock.
4. When equipment is physically released, an Admin releases the approved request. The system locks affected rows, verifies availability, reduces `available_stock`, and makes the transaction `Active`.
5. On return, an Admin records one or more item quantities. Stock is restored per item. The transaction becomes `Partially Returned` until every item is returned, then `Returned`.

Admin-created direct loans skip the request stage: stock is checked and reduced while the `Active` loan is created.

## Inventory rules

- `total_stock` is the owned quantity; `available_stock` is the quantity not currently released.
- Status is derived, not stored independently: `Available` when all stock is available, `Low Stock` when some is released, and `Out of Stock` at zero availability.
- Equipment cannot be released beyond availability. Pending and approved User requests are also considered when accepting a new request, preventing overbooking.
- An equipment total cannot be reduced below the quantity already borrowed.
- Equipment and borrowers cannot be deleted while they are part of an active or partially returned loan.
- Return quantities must be positive, belong to the selected borrowing, and not exceed the outstanding quantity. Restored availability cannot exceed total stock.

## Data model

The database must provide these tables and relationships:

| Table | Purpose |
| --- | --- |
| `users` | Login identity, profile data, hashed password, role, and account status. |
| `equipment` | Equipment name, category, total/available stock, unit type, and timestamps. |
| `borrowers` | Borrower contact data; may be linked to `users` through `user_id`. |
| `borrowings` | One loan/request header: borrower, processor, dates, purpose, notes, status, and timestamps. |
| `borrowing_items` | Equipment lines for a borrowing; borrowed, returned, and remaining quantities. |
| `return_records` | Each recorded return against a borrowing item, including receiver, date, quantity, and notes. |
| `audit_logs` | Actor, action, affected table/record, description, and timestamp. |

The `borrowings` status values used by the application are `Pending`, `Approved`, `Rejected`, `Cancelled`, `Active`, `Partially Returned`, and `Returned`.

## Main pages and APIs

| Area | Page | Read API |
| --- | --- | --- |
| Authentication | `/`, `/signup`, `/about` | `/api/session` |
| Admin dashboard | `/dashboard` | None |
| Staff dashboard | `/staff-dashboard` | None |
| Equipment | `/equipment` | `/api/equipment` |
| Borrowers | `/borrowers` | `/api/borrowers` |
| Direct borrowings | `/borrowings` | `/api/borrowable-equipment` |
| Request review | `/admin/borrowing-requests` | `/api/admin/borrowing-requests` |
| Returns | `/returns` | `/api/returnable-borrowings`, `/api/borrowings/<id>/items` |
| Reports | `/reports` | `/api/reports` |
| Audit logs | `/audit-logs` | `/api/audit-logs` |
| Staff equipment | `/staff/equipment` | `/api/staff/equipment` |
| Staff requests | `/staff/requests` | `/api/staff/requests` |
| Staff borrowed items | `/staff/borrowed-items` | `/api/staff/borrowed-items` |

## Architecture map

| Location | Responsibility |
| --- | --- |
| `app.py` | Application factory, JSON date serialization, error handling, and startup. |
| `config.py` | Environment-based Flask and MySQL configuration. |
| `auth.py` | Session guards, role checks, password-strength rule, and redirects. |
| `database.py` | MySQL connection context manager, audit helper, and shared status SQL. |
| `services.py` | Stock release/return transactions, reservation checks, and dashboard metrics. |
| `validators.py` | Server-side parsing and validation for equipment, borrowers, loans, requests, and returns. |
| `routes/` | Flask API, session, validation, and form-action blueprints. |
| `frontend/` | Next.js pages, styling, and same-origin Flask API proxy. |
| `tests/` | Route, authentication, validation, service, and return-flow tests. |

## Security and integrity notes

- Passwords are hashed with Werkzeug; the password rule requires uppercase, lowercase, number, and symbol characters.
- Validate inputs on the server even when the browser also validates them.
- Multi-step release and return actions use database transactions and row locks (`FOR UPDATE`) to avoid concurrent stock errors.
- Use `log_audit(...)` for material state changes so the audit trail remains complete.
- The generic exception handler avoids exposing internal errors to ordinary users. For APIs, it returns a safe error message.

## Development guidance

- Add new routes as blueprints and register them in `routes/__init__.py`.
- Keep stock-changing logic in `services.py`, not only in route handlers.
- Preserve the distinction between request approval (no stock change) and release (stock deduction).
- Add or update tests in `tests/` whenever business rules change. Run them with `pytest`.
- Do not commit production secrets. Configure `FLASK_SECRET_KEY` and MySQL credentials in the deployment environment.

## Related documentation

- `SYSTEM_DOCUMENTATION.md` - project overview, objectives, requirements, and feature inventory.
- `TECHNOLOGY_AND_AI_TOOLS.md` - technology and AI-tool documentation.
- `RBAC_IMPLEMENTATION_PLAN.md` - role-based access-control implementation notes.

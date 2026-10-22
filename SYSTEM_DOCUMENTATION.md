# Barangay Equipment Borrowing System

## 1. System Title

**Barangay Equipment Borrowing System**

The Barangay Equipment Borrowing System is a web-based application for managing barangay-owned reusable equipment and the borrowing process. It supports two user roles: **Admin**, who manages inventory and transactions, and **User**, who can browse available equipment, submit borrowing requests, and monitor their own requests and borrowed items.

## 2. Problem Statement

Barangays commonly lend equipment for community activities and other authorized uses. When inventory, borrower information, approvals, releases, and returns are recorded manually, staff may have difficulty determining which items are available, who is responsible for borrowed items, and whether an item has been returned. Manual records can also be incomplete, difficult to search, and prone to duplicate or inconsistent entries.

The system addresses these issues by providing a centralized, database-backed process for recording equipment, borrowers, borrowing requests, releases, returns, reports, and audit activities. It helps barangay personnel maintain accurate inventory availability and improve accountability throughout the borrowing lifecycle.

## 3. Objectives

### General Objective

To develop a web-based system that efficiently manages barangay equipment inventory and borrowing transactions while improving availability tracking, accountability, and record retrieval.

### Specific Objectives

- Provide secure account registration, login, logout, and role-based access for Admin and User accounts.
- Maintain equipment records, including name, category, quantity, unit type, and available stock.
- Maintain borrower records with contact and address information.
- Allow User accounts to view available equipment and submit borrowing requests with quantities, purpose, needed date, and expected return date.
- Allow Admin users to review, approve or reject requests, release approved equipment, and record direct borrowing transactions.
- Track active, partially returned, and completed borrowing transactions.
- Record full or partial equipment returns and update available stock accordingly.
- Provide reports for equipment availability and borrowing history.
- Preserve an audit trail of important system actions for accountability.

## 4. System Features and Requirements

### Functional Features

| Module | Features |
| --- | --- |
| Authentication | Account signup, password-strength validation, login by username or email, logout, and session-based access control. |
| Role management | Admin-only controls for inventory, borrowers, transaction processing, reports, and audit logs; User-only views for personal requests, borrowed items, equipment availability, and profile access. |
| Dashboard | Displays equipment, available-stock, active-borrowing, and borrower summaries. A separate User dashboard displays account-related borrowing statistics. |
| Equipment inventory | Add, edit, delete, search, and list equipment. The system identifies available, low-stock, and out-of-stock items. |
| Borrower management | Add, edit, view, and delete borrower records, subject to active-loan checks. |
| Borrowing requests | Users can submit requests. Admin can review pending requests, approve or reject them, and release approved equipment. |
| Borrowing transactions | Admin can create borrowing records, assign one or more equipment items, specify quantities and expected return dates, and prevent quantities from exceeding availability. |
| Returns | Record complete or partial returns, update remaining quantities, update inventory availability, and mark completed transactions as returned. |
| Reports | Generate equipment availability, active borrowing, returned borrowing, transaction, and borrower-history reports with filtering options. |
| Audit trail | Records system actions with the user, action type, affected table/record, description, and timestamp. |

### Technical Requirements

- **Application framework:** Python with Flask 3.x.
- **Database:** Supabase, accessed through the HTTPS Data API and transactional RPC functions.
- **Client technologies:** HTML5, CSS3, and JavaScript.
- **Web browser:** A current browser such as Google Chrome, Microsoft Edge, Mozilla Firefox, or Safari.
- **Server environment:** Python 3 and a Supabase project. Run the supplied SQL migrations in the Supabase SQL Editor, then set `SUPABASE_URL` and the private `SUPABASE_SECRET_KEY` in the server environment.

### Data and Security Requirements

- The database must contain the required tables for users, equipment, borrowers, borrowings, borrowing items, return records, and audit logs.
- Users must provide complete registration details. Passwords must include uppercase and lowercase letters, a number, and a symbol.
- Passwords are stored using password hashes rather than plain text.
- Server-side validation is applied to essential inputs such as quantities, dates, contact details, and equipment availability.
- Access to restricted functions is checked on the server according to the authenticated user role.
- Database changes that affect borrowing and return records are processed as transactions to help preserve data consistency.


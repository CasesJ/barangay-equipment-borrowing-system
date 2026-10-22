# Role-Based Access Control (RBAC) Implementation Plan

## Project Context

This document defines the planned Role-Based Access Control (RBAC) requirements for the **Barangay Equipment Borrowing System**. It is a planning document only: items described here are intended requirements and must not be interpreted as confirmation that they are already implemented.

The system uses Supabase through its Data API and transactional RPC functions. The existing `users` table provides two roles:

- `Admin`
- `Staff`

The RBAC enhancement must build on the existing sign-in/sign-up process, session flow, database connection, interface, and working modules. It must not require a separate application, duplicate dashboards, or an unnecessary database redesign.

## Goal

Implement a single shared system whose navigation, controls, and server-side permissions respond to the authenticated user's role.

The role must come from the trusted login/session flow. It must never be accepted from a form field, URL parameter, hidden input, or client-side JavaScript.

## Planned RBAC Flow

```text
User opens the login page
        ->
User submits username and password
        ->
System verifies the credentials
        ->
System reads the user's role from the users table
        ->
System stores trusted identity details in the session
        ->
User enters the shared dashboard
        ->
System checks the session role for each page and action
        ->
Admin: full administrative access
Staff: operational access without administrative delete/user/audit actions
```

## Session and Login Requirements

After successful authentication, the session should contain the information needed to identify the current user:

```text
user_id
full_name
username
role
```

Planned login behavior:

- Retrieve the role together with the user's account record from the Supabase `users` table.
- Store the retrieved role in the existing session structure.
- Reuse the existing login and sign-up process; change it only where necessary to include the role in the session.
- On logout, destroy the session, remove the stored role, and redirect the user to the sign-in page.

## Permission Matrix

| Feature or Action | Admin | Staff |
| --- | --- | --- |
| View dashboard | Allowed | Allowed |
| View equipment | Allowed | Allowed |
| Add equipment | Allowed | Allowed |
| Edit equipment | Allowed | Allowed |
| Delete equipment | Allowed | Not allowed |
| View borrowers | Allowed | Allowed |
| Add borrower | Allowed | Allowed |
| Edit borrower | Allowed | Allowed |
| Delete borrower | Allowed | Not allowed |
| Process borrowing | Allowed | Allowed |
| Process returning | Allowed | Allowed |
| View and print reports | Allowed | Allowed |
| Access user management | Allowed | Not allowed |
| Add, edit, or delete users | Allowed | Not allowed |
| Access audit logs | Allowed | Not allowed |

## Interface Requirements

The existing shared dashboard and sidebar/navigation must be retained. The system should conditionally display controls according to the current authenticated role.

### Admin interface

- Show all navigation entries and administrative controls.
- Show User Management and Audit Logs/Audit Trail.
- Show delete actions for equipment, borrowers, users, and other administrative records.

### Staff interface

- Show normal operational modules: Dashboard, Equipment, Borrowers, Borrowing, Returning, and Reports.
- Hide User Management and Audit Logs/Audit Trail from navigation.
- Hide or disable equipment, borrower, user, and other administrative delete controls.
- Do not duplicate the dashboard; use conditional navigation and controls in the existing shared interface.

## Server-Side Security Requirements

Hiding a button is not a security control. Every protected page and administrative action must independently verify the authenticated session role on the server.

The implementation should include a reusable Admin authorization check. The project language and existing coding style determine its final syntax, but its behavior must be equivalent to:

```text
If the session has no role, or the role is not Admin:
    deny the request before performing the protected action.
```

Apply this check before:

- Equipment deletion.
- Borrower deletion.
- User management pages and user create, edit, or delete actions.
- Audit-log pages and data endpoints.
- Any other administrative-only operation.

When a Staff user directly visits an Admin-only URL or submits an Admin-only request, the server must deny the request and must not change database data.

## Module-Specific Plan

### Equipment Management

- Preserve the existing equipment interface.
- Allow Admin and Staff to view, add, and edit equipment.
- Show the Delete Equipment control only to Admin users.
- Protect the corresponding delete operation with a server-side Admin check.

### Borrower Management

- Preserve the existing borrower interface.
- Allow Admin and Staff to view, add, and edit borrower records.
- Show the Delete Borrower control only to Admin users.
- Protect the corresponding delete operation with a server-side Admin check.

### User Management

- Make the entire User Management module Admin-only.
- Hide it from Staff navigation.
- Reject direct access by Staff users with an appropriate access-denied response.

### Audit Logs

- Make the Audit Logs/Audit Trail module Admin-only.
- Hide it from Staff navigation.
- Reject direct page or endpoint access by Staff users.

## Constraints

- Do not create separate Admin and Staff application builds.
- Do not create separate Admin and Staff dashboards.
- Do not replace the existing sign-in/sign-up system.
- Do not remove existing working features.
- Do not change the database structure unless it is necessary.
- Reuse the existing `users.role` field, session structure, database connection, UI design, and layout where applicable.
- Keep modifications focused, beginner-friendly, and free of unnecessary frameworks or libraries.

## Implementation Preparation Checklist

Before code changes, inspect the project and identify the current files or modules responsible for:

1. Login/sign-in and sign-up.
2. Session initialization and access checks.
3. Dashboard and shared sidebar/navigation.
4. Equipment management and its delete operation.
5. Borrower management and its delete operation.
6. Borrowing and returning transactions.
7. User Management.
8. Audit Logs.
9. Logout.
10. Database connection.

For each proposed change, the implementation documentation should state the relevant file, where the change belongs, the exact adapted code, and a short explanation. The code must be based on the actual project structure discovered during inspection rather than assumed PHP filenames or session variables.

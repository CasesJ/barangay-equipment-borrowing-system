# Technology and AI Tools Used

This document identifies the technologies used by the **Barangay Equipment
Borrowing System**. It reflects the current source code and dependency files.

## Technology Used

| Technology | Purpose in the System |
| --- | --- |
| Python 3 | Primary programming language used to implement the server-side application logic, validation, services, and database operations. |
| Flask 3.x | Web application framework used to create the application, register routes, manage requests and responses, render pages, and maintain sessions. |
| MySQL | Relational database used to store user accounts, equipment records, borrowers, borrowing transactions, return records, and audit logs. |
| `mysql-connector-python` | Python database driver used by the application to connect to MySQL and execute database queries and transactions. |
| HTML5 | Markup language used to structure the system pages, forms, tables, and navigation. |
| CSS3 | Styling technology used to create the visual layout, responsive views, tables, forms, buttons, and print-friendly reports. |
| JavaScript (ES6) | Client-side language used for dynamic page behavior, form interaction, filtering, fetching data from API routes, and report previews. |
| Jinja templates | Flask's server-side templating approach, used to insert authenticated-user details, dates, messages, and page data into HTML pages. |
| Werkzeug | Flask-supported utility library used for password hashing and password verification, secure routing support, and HTTP error handling. |
| Pytest | Testing framework used by the project test suite to verify authentication, validation, services, routes, and return-processing behavior. |

## AI Tools Used

| AI Tool | Purpose in the System |
| --- | --- |
| No AI tool or AI model is currently integrated | The current application does not contain an AI API, machine-learning model, chatbot, recommendation engine, or automated decision-making component. Borrowing approvals, stock validation, reporting, and role checks are handled by application rules and MySQL data. |

## Important Note

AI-assisted tools that may have been used while developing the project should
be documented separately from the running system. They are development aids,
not system features, unless their use and purpose are verified and an AI
service is actually integrated into the application.

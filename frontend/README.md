# Next.js frontend

This is the React/Next.js frontend for the existing Flask/Supabase backend. It intentionally preserves the Flask API, validation, RBAC, audit logging, and session behavior.

1. In the repository root, start the existing backend with its virtual environment: `.\.venv\Scripts\python.exe app.py`.
2. In this directory, install dependencies: `npm install`.
3. Start Next.js: `npm run dev`.
4. Open `http://localhost:3000`.

All Flask requests pass through `/api/proxy/*`, a Next.js route handler that
forwards the Flask session cookie and redirects. Set the server-only
`FLASK_API_URL` for every environment; it must be the HTTPS backend origin in
Vercel production.

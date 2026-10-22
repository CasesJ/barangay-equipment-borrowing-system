# Deployment guide

This project deploys as two services:

- **Vercel:** the Next.js application in `frontend/`.
- **Python web service:** Flask at the repository root, which alone connects to Supabase.

The browser talks only to the Vercel origin. Next.js forwards every Flask call
through `/api/proxy/*`, including the Flask session cookie. Consequently, a
browser-to-Flask CORS policy is neither required nor desirable for this
architecture.

## Vercel

1. Import the repository and set the project's **Root Directory** to
   `frontend`.
2. Use the detected Next.js framework with `npm ci` as the install command and
   `npm run build` as the build command.
3. Set this server-only environment variable for both Preview and Production:

   ```text
   FLASK_API_URL=https://your-backend.example.com
   ```

   Do not use a `NEXT_PUBLIC_` prefix. Preview must point to a separate
   staging backend (and staging Supabase project) so preview actions cannot
   change production data. Do not put `SUPABASE_SECRET_KEY`,
   `FLASK_SECRET_KEY`, or any database credential in Vercel.
4. Deploy a Preview first, then set a production domain and redeploy with the
   production backend URL.

## Flask service

Deploy the repository root as a Python web service. A Render configuration is:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn --workers 2 --bind 0.0.0.0:$PORT app:app
Health check path: /api/health
```

Set these environment variables on the Flask service. Enter real values only
in the hosting provider's secret manager; never commit them.

```text
APP_ENV=production
FLASK_DEBUG=false
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
FLASK_SECRET_KEY=<long-random-secret>
SUPABASE_URL=<your-supabase-project-url>
SUPABASE_SECRET_KEY=<your-sb_secret-service-key>
```

`/api/health` only confirms that Flask is running. It intentionally does not
query Supabase, so a successful health check is not proof of database access.

## Deployment validation

After both services are deployed, verify through the Vercel URL:

1. `GET /api/proxy/api/health` returns `{"status":"ok"}`.
2. Unauthenticated `GET /api/proxy/api/session` returns `401`.
3. In a non-production test account, log in, refresh the page, log out, and
   verify that Admin and User accounts receive only their permitted screens.
4. Use a controlled test transaction to verify request submission, approval,
   release, return, stock updates, audit records, and reports.

Do not direct browser requests to the Flask URL, and do not enable permissive
CORS for the Vercel application. The existing Supabase RPC functions remain
unchanged and continue to run from Flask with its server-only key.

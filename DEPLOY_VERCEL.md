# Deploy the dashboard on Vercel

This repository currently runs a React/Vite frontend and a FastAPI backend. The
backend continuously syncs Test3 and writes a SQLite cache. Deploy the frontend
on Vercel and run the existing backend on a persistent server/container.
Vercel Functions do not provide the shared persistent disk this backend needs.

## 1. Start the backend on its host

An ignored backend/.env.production has been prepared with the existing Test3
spreadsheet settings and a newly generated session-signing secret. Import this
file into the backend host's environment. Do not upload it to the frontend
project. A tracked backend/.env.production.example documents the same settings
without a secret.

Keep a persistent volume mounted at /app/data when using the existing Docker
image. The database path in this file is for the container; replace it with the
host's actual persistent-disk path for a non-container deployment.

Use the existing image/Dockerfile to run one backend process. Provide its public
HTTPS address through your host's reverse proxy. Its internal port is 8000.

To build/run the existing Docker Compose service with the production variables:

    docker compose --env-file backend/.env.production up -d --build

The existing Compose file mounts ./backend/data at /app/data. Its container API
is exposed on port 8000; HTTPS/domain configuration belongs to the backend host.
The bundled dashboard may also be served by that container, but Vercel will host
the public dashboard for this setup.

Verify the public API before configuring Vercel:

    https://YOUR-BACKEND-DOMAIN/api/health

The response should show status=online, visit_data_source=google_sheets, and
database=market_reports_sheets_test3.db. The Users tab remains the login source.

If the spreadsheet becomes private, mount the service-account JSON read-only,
grant its account Viewer access to the workbook, and set
GOOGLE_SHEETS_CREDENTIALS_FILE to its mounted path. This credential stays on the
backend host.

## 2. Configure the Vercel project

Import the repository and use:

| Setting | Value |
| --- | --- |
| Root Directory | frontend |
| Framework Preset | Vite |
| Install Command | npm ci |
| Build Command | npm run build |
| Output Directory | dist |

frontend/vercel.json supplies the build settings and SPA fallback. The Root
Directory still needs to be selected in Vercel's project settings.

Add this environment variable to the Vercel project:

    VITE_API_BASE_URL=https://YOUR-BACKEND-DOMAIN/api

Use the actual public HTTPS backend hostname, include /api, and omit the trailing
slash. The exact value is the only missing deployment input because the backend
has not been deployed yet. frontend/.env.example is a copyable template.

Set the variable for Production and for Preview if preview deployments should
use that backend. The browser sends API requests directly to this URL using the
existing bearer-token login. The backend already permits cross-origin requests;
its CORS settings can be narrowed once the final frontend hostname is known.

Vite embeds this public API URL at build time. Create a new Vercel deployment
after setting or changing it. The Vite localhost proxy works only in development;
Vercel will not use the localhost:8000 proxy configuration.

Only VITE_API_BASE_URL belongs in the Vercel frontend environment for this app.
AUTH_SECRET_KEY, Sheet credentials, database paths, and Telegram tokens stay on
the backend. VITE_ variables are public in the built JavaScript.

## 3. Verify the deployed dashboard

- Open the Vercel deployment URL and sign in using the existing Users account.
- Confirm Sales Activity and Drop Calendar show Test3 data.
- Confirm the browser's /auth/login request goes to the public backend /api URL.
- Make a Sheet edit and allow roughly 30 seconds plus loading time: backend sync
  runs every 15 seconds and the dashboard polls every 15 seconds.
- Open a nested frontend URL directly to check the SPA fallback.

For local development, leave frontend/.env unset so the existing /api localhost
proxy continues to work. The root .env remains your existing local setup.
The backend does not automatically load a file named .env.production; import it
into the host's environment or pass it to Docker as shown above.

## References

- [Vercel Vite deployment](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel build and Root Directory settings](https://vercel.com/docs/builds/configure-a-build)
- [Vercel environment variables](https://vercel.com/docs/environment-variables)
- [SQLite and Vercel Functions](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel)
- [Vite 5 environment variables](https://v5.vite.dev/guide/env-and-mode)

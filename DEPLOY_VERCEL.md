# Deploy both services on Vercel

The root vercel.json builds two services in one project:
- frontend: static React/Vite dashboard, public at /.
- backend: Python 3.12 FastAPI, public at /api and /api/*.

The original request path is preserved: FastAPI already defines /api/auth/login,
 /api/activity/*, and the other /api routes. Backend /docs and /openapi.json
are not publicly routed by this configuration.

## Bindings

No bindings are needed in the current architecture. Vite serves static files;
browser fetches use the public same-origin /api path. There is no frontend
server function calling the backend. Runtime binding URLs must not be embedded
in VITE_ variables or browser bundles. Google Sheets is an external data source,
not another Vercel service. Add a caller-side binding if server-side calls are
introduced later.

## Deployment steps

1. Set the Vercel project Root Directory to the repository root (./).
2. Select the Services preset. Remove project-wide frontend install/build/output
   overrides; these are now specified on the frontend service.
3. Import the prepared, ignored root .env.vercel file into Vercel. It contains
   the Test3 / Users configuration and a private signing secret. Only the public
   VITE_API_BASE_URL=/api value belongs in frontend code. Keep the signing secret
   stable across instances and deployments; changing it signs out active users.
   Do not import backend/.env.production for this setup: that file describes a
   persistent Docker host. frontend/.env.vercel now only documents /api.
4. Remove any old VITE_API_BASE_URL pointing to Render or a placeholder. The
   Vercel frontend build also enforces /api to prevent stale cross-deployment URLs.
5. Deploy from the repository root after confirming the proposed names, public
   paths, and absence of internal bindings.
6. Check /api/health, sign in using a Users account, and verify the map,
   RM activity, channel permissions, unread filter, and Drop Calendar.

A tracked .env.example lists the shared settings without a secret. Never commit
the private .env.vercel. The existing Render deployment is independent and is not
changed by these files.

## Function storage and refresh behavior

Vercel mode is detected with VERCEL=1, including local vercel dev. A process-local
SQLite file under the runtime temporary directory is a disposable read cache,
never the source of truth. DATABASE_PATH is ignored in this mode so a stale
Docker /app/data or Windows path cannot break startup. Test3 is fetched on the
first authenticated data request. Further requests refresh it at most once per
15 seconds per instance. The dashboard continues polling every 15 seconds.
There is no guaranteed background refresh while nobody is using the dashboard.

Concurrent cold requests share one refresh. A failed cold fetch returns 503;
a warm instance can continue serving its last complete snapshot. A fresh
function instance rebuilds independently from the Sheet. No SQLite database
or customer records are packaged in the deployment.

Transaction file uploads are rejected on Vercel because they require durable
storage; accepting them into temporary storage would lose them on recycling.
Existing persistent Docker/Render deployments keep their upload behavior.
Telegram polling also requires the existing persistent deployment; Vercel mode
supports the Google Sheets monitoring source. Users-directory caches, login
throttling, and token revocation remain process-local, not distributed across
function instances. A shared durable store is needed before relying on global
rate limits, global immediate revocation, or transaction uploads on Vercel.

The backend build command packages the shared boundary JSON from frontend source
into backend/boundaries. All other static frontend assets stay in the Vite
service. The backend does not mount the frontend in Vercel mode.

## Local verification

Install Python 3.12 and ensure it is selected by your shell before starting
vercel dev; the current Vercel Python runtime package requires Python >=3.12.
The backend/.python-version file pins the hosted runtime to 3.12.

From the repository root, use the current Vercel CLI:

    npx vercel@latest dev --local

For a linked project use:

    npx vercel@latest dev

The CLI runs the services and top-level routing together. Set the shared
environment variables listed in .env.example (or import them into the linked
project); do not set generated binding variables yourself. Plain Python/Vite
local development and the existing Docker/Render workflow remain supported.

## References

- https://vercel.com/docs/services
- https://vercel.com/docs/services/bindings
- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes

## Verification in this workspace

- Frontend TypeScript/Vite production build passed with VERCEL=1 and an
  intentionally obsolete API URL. No obsolete hostname appears in its bundles.
- 73 affected backend tests passed, including function cold starts, concurrent
  refreshes, failed Sheet reads, channel access, and login behavior.
- Root configuration passed the published Vercel JSON schema.
- Vercel CLI 65.2.0 detects both services. Full local startup is unverified:
  this workstation only has Python 3.11, while vercel-runtime requires >=3.12.
- The broader backend suite has six sales-test failures and one setup error:
  old tests expect anonymous access and depend on local data. The same failures
  were reproduced against the unchanged deployed-code worktree.

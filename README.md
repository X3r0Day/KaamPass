# KaamPaas

KaamPaas connects workers and small employers in **Ghaziabad district, Uttar Pradesh**. Find short-term work or a permanent job by trade, locality, and postal PIN. Sign in with an SMS code; use the site in English or हिन्दी. The launch catalog covers 21 areas across seven PINs.

- Workers choose when employers can find them, accept invitations, and see their applications and reported earnings.
- Employers publish openings, invite eligible workers, and close assignments as completed work or permanent hires.
- Optional voice input becomes an editable draft. A “Listen” button reads the structured listing aloud. All actions also work without a microphone.
- The site doesn't move money. Dial-in keypad access, WhatsApp, and messaging are not part of this release.

## Run locally

Requires Docker Compose, Python 3.12 (`uv`), and Node 24. Run these commands from the repository root:

```sh
bash scripts/local.sh
docker compose up -d --wait db
(cd apps/api && uv sync --locked)
npm ci --prefix apps/web
npm ci --prefix tests/e2e
(set -a; source .env; cd apps/api && uv run alembic upgrade head)
```

In three terminals, from the root:

```sh
./tests/e2e/node_modules/.bin/firebase emulators:start --project demo-kaampaas --only auth
```
```sh
set -a; source .env
cd apps/api && uv run uvicorn main:app --host 127.0.0.1 --port 18031 --reload --no-access-log
```
```sh
set -a; source .env
cd apps/web && npm run dev -- --hostname 127.0.0.1
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Locally, the Auth Emulator prints verification codes to its terminal instead of sending real SMS. Only a loopback `demo-` project may use emulation. Local speech is optional; add separate speech credentials to the ignored `.env` to exercise the cloud provider.

## Verify changes

```sh
(set -a; source .env; cd apps/api && uv run ruff check . && uv run pytest -q)
(cd apps/web && npm run lint && npm run typecheck)
(cd tests/e2e && npx playwright install chromium && npm test)
```

Keep the three services running for Playwright. To use a system browser, supply `CHROMIUM_PATH=/path/to/chromium`. Tests cover the two-role shift/permanent flows, scoped contact and earnings, matching order, assignment concurrency, and the microphone-denied flow. They do not send SMS.

After API contract changes:

```sh
(cd apps/api && uv run python export_contract.py)
npm run contract --prefix apps/web
```

## Deploy to Vercel

1. Import the **private** GitHub repository, `X3r0Day/delhi4`, with the repository root as the Vercel project root. `vercel.json` deploys `apps/web` and `apps/api` as separate services under one HTTPS hostname. Select Node 24. Keep `/api/(.*)` routed before the catch-all.
2. Create separate production and staging projects in Firebase, and separate Neon databases or branches. Enable Phone Auth and Blaze billing. Authorize only the corresponding stable Vercel/custom domain and allow India under the project's SMS region policy. Use Firebase web app public configuration in the web build. Enable Cloud Speech-to-Text and Text-to-Speech, grant only the IAM permissions required by those services, set budgets/alerts, and configure server credentials separately.
3. Set the variables below in the appropriate environments. Scope preview credentials to preview/staging data, not production. Apply migrations once before promotion. For the first deployment, configure protected approvals for the GitHub `production` environment and set its `MIGRATION_DATABASE_URL` secret. Run **Checks** manually on `main` to apply migrations after test success and approval. For subsequent releases, use backward-compatible migrations; apply them before promoting the build that uses them. A Vercel rollback does not roll back the schema.
4. On a preview domain, check `/api/health`, sign-in, the same-origin cookie, and the Hindi and English recording/readback flows. Test Android Chrome and iOS Safari with mic enabled and denied. Before announcing production, repeat registration and both hire types with real Indian phone numbers and real speech credentials. Monitor delivery, error rates, quotas, and backups.

| Variable | Where | Value |
|---|---|---|
| `NEXT_PUBLIC_FIREBASE_{API_KEY,APP_ID,AUTH_DOMAIN,PROJECT_ID}` | Web build | Firebase web config; public identifiers, not Admin credentials |
| `FIREBASE_PROJECT_ID`, `FIREBASE_ADMIN_JSON` | API | Matching project and server-side Firebase Admin JSON |
| `WEB_ORIGINS`, `CSRF_SECRET` | API | Comma-separated exact HTTPS origins; independent random secret, at least 32 bytes |
| `DATABASE_URL` | API | Neon pooled URL with `sslmode=require` or stricter; limited runtime role |
| `MIGRATION_DATABASE_URL` | Protected release job | Direct Neon URL with TLS; schema migration role |
| `SPEECH_CREDENTIALS_JSON` | API | Google Cloud service account JSON for speech, not exposed to Next.js |
| `SPEECH_MODEL`, `TTS_VOICE_EN`, `TTS_VOICE_HI` | API (optional) | Override verified recognition model and en-IN/hi-IN voices |

Do not set emulator URLs or local proxy variables on Vercel. Keep service credentials out of Git, logs, and frontend env variables. There are no production sample accounts or jobs. If using custom analytics, omit numbers, audio, SMS codes and contact links.

## Edit the product

- **Language and layout:** `apps/web/src/content`, `apps/web/src/styles/site.css`.
- **Trades and coverage:** `apps/api/reference_data`; edit the import selection and create a new Alembic revision for a deployed database. See [catalog provenance](apps/api/reference_data/SOURCE.md).
- **Matching and hiring rules:** `apps/api/app/services/matching.py` and `hiring.py`. Keys and recent phone identity are enforced by the API, not by the UI.
- **Full release and future dial-in plan:** [PLAN.md](PLAN.md).

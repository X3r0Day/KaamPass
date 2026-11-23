# KaamPaas

KaamPaas connects workers and small employers in **Ghaziabad district, Uttar Pradesh**. Find short-term work or a permanent job by trade, locality, and postal PIN. Sign in with an SMS code; use the site in English or हिन्दी. The launch catalog covers 21 areas across seven PINs.

- Workers choose when employers can find them, accept invitations, and see their applications and reported earnings.
- Employers publish openings, invite eligible workers, and close assignments as completed work or permanent hires.
- Optional voice input becomes an editable draft. A “Listen” button reads the structured listing aloud. All actions also work without a microphone.
- The site doesn't move money. WhatsApp registration, nearby search, and basic job posting are supported through the bot below. Dial-in keypad access and in-app chat remain out of scope.

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

## Run the WhatsApp bot

**Paused for the current deployment.** The WhatsApp menu entry stays visible, but it does not open a conversation and the webhook is disabled. Leave `WHATSAPP_ENABLED=false` until the Meta number is verified and the webhook is ready.

No website OTP or Firebase credentials are needed in WhatsApp-only mode:

1. In Meta, create a WhatsApp Cloud API business app and connect a WhatsApp Business number. Set a Meta token with `whatsapp_business_messaging` access to that number. On a test number, add the recipients you will actually test with.
2. Put these **server-side** Vercel variables in the environment for the API (or the ignored `.env` for local use):

   | Variable | What goes here |
   |---|---|
   | `WHATSAPP_ENABLED` | Set `true` in both services to turn on the bot and its menu link. Defaults to off |
   | `WHATSAPP_PHONE_NUMBER_ID` | Meta's internal number ID from API Setup; **not** the dialable number |
   | `WHATSAPP_ACCESS_TOKEN` | Cloud API access token; use a suitable system-user token for a continuing deployment |
   | `WHATSAPP_APP_SECRET` | Meta application secret used to verify signed webhook bodies |
   | `WHATSAPP_VERIFY_TOKEN` | Independently generated random value. Enter the same value in Meta's webhook setup |
   | `WHATSAPP_GRAPH_VERSION` | Optional, defaults to `v26.0` |
   | `TOKEN_HARBOR_API_KEY` | Token Harbor server key; [`deepseek-v4.1-flash:free`](https://tokenharbor.ai/docs/integrations/claude-code-deepseek) only |
   | `SPEECH_CREDENTIALS_JSON` | Google service account JSON for [Cloud Speech-to-Text](https://docs.cloud.google.com/speech-to-text/docs/encoding) |
   | `WHATSAPP_PUBLIC_NUMBER` | Public dialable number in international format, digits only. This enables the `wa.me` CTA |
   | `WEB_PHONE_AUTH_ENABLED` | `false` for both services; this is Vercel's default. The local web setup still uses the Firebase emulator |

   Keep `DATABASE_URL`, `WEB_ORIGINS`, and `CSRF_SECRET` set. Enable Token Harbor's free-model data sharing in its dashboard if required by your account. The bot offers its own explicit Voice + AI opt-in; guided text does not use Google or Token Harbor. No paid model fallback is configured.
3. Apply `0003_whatsapp` with `uv run alembic upgrade head` before routing production messages. In Meta, set the callback to `https://YOUR_DOMAIN/api/whatsapp/webhook`, use the verification token above, and subscribe to `messages`. A public HTTPS route is required; open the website on a mobile device or WhatsApp Web and send `Hi` to the configured number. The registration confirmation is a native WhatsApp **Yes** button, not a website form.
4. Try `Role: Worker`, `Name: …`, `Area: Duhai`, `Trade: Mason` and `Type: short-term` on separate lines. The bot asks only for missing fields, then waits for confirmation. In Voice + AI mode, the same details can be spoken in a WhatsApp voice note (up to 45 seconds). Google transcribes the note and the free DeepSeek model extracts known fields. The API, not the model, validates and creates the profile.
5. As a worker, ask for `nearby jobs`, `invitations`, `applications`, `availability`, or `my profile`. When a numbered nearby list appears, `apply 1` opens a separate contact-sharing confirmation. As an employer, enter `post a job` to draft a listing, then confirm it with **Publish**. `my postings` checks statuses. The complete assignment/closure UI remains the website's employer board when its authentication is enabled.

WhatsApp and the website use the same profile/public ID and job tables. A second channel independently verifies the number and asks the user to connect the existing profile; it does not create a second account or overwrite fields. Provider calls never receive a WhatsApp sender ID or full profile; Voice + AI sends the provided text/transcript after basic phone/email redaction. Avoid sharing addresses or identity documents in chat. The application does not retain raw audio or full messages. Completed outbound payloads are cleared; incomplete drafts expire after seven days, and stale deduplication rows are cleaned on traffic.

### Deploy the website

1. Import the **private** GitHub repository, `X3r0Day/delhi4`, with the repository root as the Vercel project root. `vercel.json` deploys `apps/web` and `apps/api` as separate services under one HTTPS hostname. Select Node 24. Keep `/api/(.*)` routed before the catch-all.
2. Use separate Neon databases or branches. Keep website SMS off for a WhatsApp-only release. **If enabling website SMS later**, create separate production and staging Firebase projects, set `WEB_PHONE_AUTH_ENABLED=true`, enable Phone Auth and Blaze billing, authorize only the corresponding stable domains, and allow India in the SMS region policy. Configure Cloud Speech-to-Text and Text-to-Speech separately and set budgets/alerts.
3. Set the variables below in the appropriate environments. Scope preview credentials to preview/staging data, not production. Apply migrations once before promotion. For the first deployment, configure protected approvals for the GitHub `production` environment and set its `MIGRATION_DATABASE_URL` secret. Run **Checks** manually on `main` to apply migrations after test success and approval. For subsequent releases, use backward-compatible migrations; apply them before promoting the build that uses them. A Vercel rollback does not roll back the schema.
4. On a preview domain, check `/api/health`, webhook verification, WhatsApp registration and both types of posting with real business messaging and speech configured. If website SMS is enabled later, verify sign-in, the same-origin cookie, and the Hindi and English recording/readback flows on Android Chrome and iOS Safari. Monitor delivery, error rates, quotas, and backups.

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

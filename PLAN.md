# Hyperlocal Job Matching — website launch plan

**Release goal:** A daily-wage worker in a non-metro town can hear about nearby work, apply, or make themselves available to local hirers. A small shop or contractor can post a one-day shift, a longer short-term job, or a permanent opening. Both can do this on the production website in Hindi or English, with real phone authentication and a durable hiring record.

**Website release:** Use a web browser; the SMS code can arrive on a separate basic phone, so a shared computer works. **Future release:** Dial one number on a feature phone and use its keypad, without a browser, mobile data, or previous website registration. Section 8 maps that future service to the website's capabilities. Do not publish a call button or claim that calls work at launch.

### How the website meets the problem brief

| Requirement from the brief | Website integration | What a judge can observe |
|---|---|---|
| Informal and semi-skilled workers miss **nearby** opportunities in non-metro areas | Use familiar trade names and verified town/village and PIN choices. Show why each job matched. No CV, GPS permission, or street address required. | A mason finds work in their selected areas; an unrelated trade or unselected area does not appear. |
| Serve **daily-wage earners and local small businesses** | Show trade, work area, pay **and its unit**, dates, and one clear action on each card. Employers post with these same fields. | A worker can tell what one shift pays, where it is, and when to turn up before expressing interest. |
| Match **short-term and permanent** openings | Use distinct opening types, worker preferences, and outcomes for a finished shift versus a filled vacancy. | A shop can hire a permanent employee without that hire appearing as a completed day job or a salary payment. |
| A **voice-enabled, localized job board** through a simple web UI | Workers can speak a trade and listen to job summaries; employers can dictate a description and review the posting aloud. Deliver the critical journey in Hindi and English. | The same job can be posted and understood using voice, or using only text and buttons when the mic is unavailable. |
| Let a worker **open themselves to hirers** | Give workers an explicit availability control and employers a shortlist tied to their own open job. | A worker appears when they opt in, can receive an invitation, and disappears from new shortlists when they pause. |

The project directory was empty at planning time. Build one FastAPI backend. Website integration is the entire first release; telephony, WhatsApp, payments, in-app chat, and an admin panel are outside it.

## 1. What people can do

Keep four web routes. Phone verification and first-time registration share `/login`.

| Route | Behavior |
|---|---|
| `/` | Put the हिन्दी / English switch above “Find work” and “Post a job.” Explain the areas served, how phone sign-in works, and that workers choose when employers can find them. |
| `/login` | Verify the number. Returning users go to their dashboard. New users choose a role, enter their details, and review before confirming. Workers select trades, work areas, and short-term work, permanent work, or both. No public ID or discoverable profile before confirmation. |
| `/dashboard` | Workers see availability first, then matches, invitations, applications, and work history. Employers can post a job, see available workers for that job, invite or review interested workers, assign one, and close the opening. |
| `/dashboard/edit` | Edit display name, preferred language, and work locality; workers can edit trades, additional work areas, and opening types. Explain which edits change future matches. Phone, role, and public ID are read-only. |

Start both dashboards at zero. A worker with no matches sees the trade, areas, and opening types searched and can change them. A new employer sees “Post your first job.” Edits never erase prior assignments.

**Design for the person reading the card:** lead with trade and pay/unit, then locality, dates, match reason, “Listen / सुनें,” and the next action. Keep labels beside icons, touch targets at least 44 px, and no autoplay. Translate field choices, errors, empty states, availability, and confirmations, not just headings. Preserve user-entered descriptions as written. Lazy-load recording and audio playback, paginate results, and keep the form usable on a narrow screen or slow connection. Give shared-device users a visible sign-out action.

## 2. Architecture and editing

| Part | Decision |
|---|---|
| Web | Next.js App Router, TypeScript, Tailwind. One typed API client; no SQL, session issuance, or matching logic in the UI. |
| API | FastAPI, Pydantic, SQLAlchemy, Alembic. Domain services own registration, availability, matching, invitations, and job transitions. They take a verified actor and structured inputs; they do not read browser cookies themselves. |
| Identity | Firebase Phone Auth for SMS verification; Firebase Admin session cookies for ongoing sign-in. No second JWT issuer. |
| Storage | Neon Postgres. Use a pooled TLS connection at runtime and a separate direct connection for migrations. |
| Web speech | Use Google Cloud Speech-to-Text and Text-to-Speech behind a small FastAPI adapter. Configure supported `hi-IN` and `en-IN` models/voices per environment. Keep speech credentials on the server. |
| Deployment | One private GitHub repository and one Vercel project. Use [Vercel Services](https://vercel.com/docs/services): route `/api/(.*)` to FastAPI **before** the catch-all route to Next.js. Both share the same HTTPS origin and deploy together. |

Proposed repository layout:

```text
apps/web/src/app/                  Pages and layouts
apps/web/src/features/             Auth, onboarding, worker and employer views
apps/web/src/lib/                  Typed API client, Firebase browser setup
apps/web/src/content/{hi,en}/      Product copy, field labels, read-aloud phrases
apps/web/src/styles/               Shared design tokens and global styles
apps/api/main.py                   FastAPI entry point (main:app)
apps/api/app/{routes,services,db}/  HTTP contracts, business rules, models
apps/api/app/integrations/speech/  Transcription and read-aloud provider
apps/api/migrations/               Versioned schema
apps/api/reference_data/           Trade aliases, locality import and source dates
tests/e2e/                         Browser journeys across both roles
vercel.json                        Service roots and routing
```

Put matching in one Python module and serve trade/locality choices from the API. Keep stable IDs separate from translated labels: `राजमिस्त्री`, `mistri`, and `mason` can resolve to the same trade. Lock dependencies, check frontend types against FastAPI's OpenAPI contract in CI, and document local start, reference-data import, migration, and release commands.

### Web voice: capture → review → confirm

1. From an authenticated onboarding or job form, the user chooses Hindi or English and taps “Speak.” Explain that a short recording is sent for transcription; request mic access only then. Stop on tap or after 15 seconds. Send one supported, size-limited clip (maximum 1 MB) to `POST /api/voice/transcribe`. This stays below the [Vercel function request limit](https://vercel.com/docs/functions/limitations).
2. The API returns a **draft** transcript. For a trade, suggest a catalog choice and let the worker select it. For a job description, put the transcript in an editable field. Confirm work area, pay/unit, dates, and opening type explicitly. A recognition error must never post a job, apply, or change availability.
3. “Listen” uses `POST /api/voice/readback` to speak a localized summary of an authorized job or the user's own structured draft: trade, area, pay/unit, dates, and type. Support replay and stop. If audio fails, keep the same visible summary and form values. Mic refusal must not block listening, typing, or submitting. Verify the chosen [recognition locales](https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages) and [synthesis voices](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types) in staging.
4. Enable speech APIs and billing explicitly; rate-limit both operations per verified user. Validate content type, size, and duration server-side. Do not save recordings or draft transcripts in the application database, storage, or logs. Persist only fields the user confirms; never record the OTP flow or read private phone numbers aloud.

## 3. Production phone authentication

1. **Provision real SMS first.** Enable Firebase's Phone provider, link the Blaze billing plan, explicitly allow India in the SMS region policy, and authorize the production hostname and a separate stable staging hostname in their respective projects. Show the phone-use/SMS consent text before sending. Firebase documents [the billing requirement](https://firebase.google.com/docs/auth/limits) and [the domain, reCAPTCHA, and region setup](https://firebase.google.com/docs/auth/web/phone-auth). Do not assume live SMS is free.
2. **Verify in the browser.** Default the country selector to India, normalize the number to E.164, use Firebase's reCAPTCHA verifier, then confirm the SMS code with Firebase. Use in-memory client auth persistence. A resend countdown helps the user; provider-side abuse controls, quotas, and usage alerts protect SMS delivery.
3. **Exchange once on the server.** Send the Firebase ID token to `POST /api/auth/session`. FastAPI verifies signature, issuer, audience, expiry, revocation, a recent `auth_time` (within five minutes), the phone sign-in provider, and the token's phone claim. Never take identity from a form field. Mint a 24-hour [Firebase session cookie](https://firebase.google.com/docs/auth/admin/manage-cookies): `__Host-session`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, no `Domain`. Clear the transient Firebase client sign-in after exchange.
4. **Protect every mutation, including login and logout.** Require the exact allowed web origin and a server-issued CSRF token in a custom header. Bootstrap the token before login, bind it to the session after login, and rotate it on session change. Use the [signed double-submit pattern](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). Apply a shared, server-side rate limit to session exchange and writes; an in-process counter does not span Vercel instances.
5. **Resolve the current user in FastAPI.** Verify the session cookie, including revocation, on protected requests. At confirmed registration, bind the verified Firebase UID to the verified phone; reject a conflicting binding rather than silently merging profiles. Domain services receive the resulting internal identity, never a phone supplied by the caller. Verified users may use voice to draft onboarding; job operations require a completed profile. Private responses use `Cache-Control: private, no-store`. On logout, revoke the user's Firebase sessions and expire the cookies; label this action “Sign out of all devices.”

Login never reveals whether a number has a profile before OTP verification. Keep OTPs, tokens, cookies, credentials, and full phone numbers out of logs, analytics, URLs, and error responses.

## 4. Data and matching rules

| Records | Invariants |
|---|---|
| `profiles`, `identity_bindings` | Canonical E.164 phone is the internal profile key; public ID is unique. One role per phone. Store display name, language, and primary work area. Keep the verified Firebase UID in a unique `(provider, subject)` binding, with at most one binding per provider per profile. The website requires Firebase; a future channel need not invent a Firebase UID. |
| `skills`, `worker_skills`, `localities`, `worker_work_areas` | Stable trade IDs with local names/aliases. A worker selects at least one trade and a primary locality; optionally select up to three more work areas in the pilot district. Localities carry district, state, and verified six-digit postal PIN. |
| `worker_preferences` | Opening types accepted, `discoverable`, and optional `discoverable_until`. Discovery is off until the worker explicitly chooses “Open today,” “Open until a date,” or “Open until I pause.” Expiry uses the end of the selected day in `Asia/Kolkata`. |
| `jobs` | UUID, employer, required trade, locality, `short_term` or `permanent`, start date, application deadline, pay in integer INR paise with unit (`shift`, `day`, `month`, or `job`), state, and timestamps. Short-term work has an end date; a one-day shift has matching dates and a local start time. A permanent opening has an application deadline but no employment end date. Default the title from trade and type; a written or dictated description is optional. |
| `invitations`, `interests` | Each is unique per `(job, worker)`. An invitation offers a choice; only a worker's explicit interest or acceptance creates an interest. Record agreement to share contact details if selected; the employer gives matching consent when posting. |
| `assignments` | One row per job, referencing an interest in that same job. Holds the selected worker and optional worker-reported amount actually received. |

**Issuing IDs:** Only the final onboarding confirmation inserts a profile. Generate `WKR-` or `EMP-` plus six random digits in the range `100000`–`999999`. Let the database enforce uniqueness on insert and retry a public-ID collision within a bounded transaction flow. A repeated confirmation by the same identity returns its existing ID. The ID is a platform reference, never proof of identity or an access key.

**Ground the pilot in real places.** Launch in **Ghaziabad district, Uttar Pradesh**, including smaller towns such as Modinagar and Muradnagar. Ghaziabad city is part of the NCR. Import the selected post-office/locality and PIN records from the Department of Posts' [PIN directory](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month), store the source date, and review user-facing names with a local speaker. Show locality **and** PIN because a PIN can serve several places. An unsupported area gets a coverage message, not a guessed match.

**Which jobs match:** Filter to open, unexpired jobs of an accepted type and selected trade. Rank (1) primary locality, (2) another locality sharing its postal PIN, then (3) an additional work area explicitly selected by the worker. Exclude everything else. Within a tier sort by newest posting and stable job ID. Return a reason code the UI can translate, such as “Mason · your locality” or “Mason · another area you chose.” A PIN is not a distance estimate. Apply the same rules when showing candidates for a job.

**Availability and invitations:** Only the owner of an open job can see its matching, opted-in, unexpired candidates; cards show trade, work area, and public ID. An invitation names the job and lets the worker listen, express interest, or decline. Recheck discoverability when sending. Pausing or expiry immediately stops new discovery and invitations; the worker can still browse, apply, and see existing invitations and assignments. No general worker directory.

**Closing the loop:** Only the posting employer can select one worker who has expressed interest. Lock the job row and create the assignment in one transaction. Short-term work goes `open → assigned → completed`. A permanent opening goes `open → assigned → filled` once the hire is confirmed. The owner can cancel an open or assigned job. Retries must not double-count. Contact details are visible to the selected pair only while assigned; explain this before the owner closes the job.

**Dashboard numbers:** Count completed short-term jobs and filled permanent placements separately. “Workers hired” counts distinct assigned workers on non-cancelled jobs. A worker can record actual pay against their own completed short-term work under **Self-reported earnings**. Never convert an advertised day rate or monthly salary into earned money.

## 5. API surface and access boundaries

| API | Access |
|---|---|
| `GET /api/auth/csrf`, `POST /api/auth/session`, `POST /api/auth/logout` | Session bootstrap, verified token exchange, sign-out. |
| `GET /api/me`, `POST /api/me/onboarding`, `PATCH /api/me` | Current user only. `GET` returns `401` without a session and `needs_onboarding` for a verified new user. `PATCH` accepts editable fields only. |
| `GET /api/skills`, `GET /api/localities`, `GET /api/me/dashboard` | Localized trade and locality lookups; authenticated, role-specific dashboard with paginated matches, invitations, and activity. |
| `PUT /api/me/availability` | Worker only. Set an explicit state and expiry rather than an ambiguous toggle; retries are safe. |
| `POST /api/voice/transcribe`, `POST /api/voice/readback` | Verified session, bounded payload, supported locale, and quotas. Read persisted job details only if that same actor can view them. |
| `POST /api/jobs`, `GET /api/jobs/{id}/interests`, `GET /api/jobs/{id}/candidates` | Employers post; only the owner sees interested workers or the job-specific available shortlist. |
| `POST /api/jobs/{id}/invites`, `POST /api/me/invitations/{id}/response` | Owner can invite a currently eligible worker. Only the recipient can accept or decline. Acceptance rechecks that the job is still open and creates an interest once. |
| `POST /api/jobs/{id}/interest`, `POST /api/jobs/{id}/assign` | Eligible worker expresses interest; owning employer chooses an existing interest. |
| `POST /api/jobs/{id}/complete`, `POST /api/jobs/{id}/fill`, `POST /api/jobs/{id}/cancel` | Owning employer only; validate opening type and state under lock. |
| `GET /api/jobs/{id}/contact`, `PUT /api/jobs/{id}/earnings` | Contact: selected pair while assigned. Earnings: assigned worker after short-term completion. |

Scope queries to the authenticated person and their relationship to the record. Never expose `/profile/{phone}` or accept a caller-supplied owner. Job and interest lists expose public IDs, not phone numbers. Validate field lengths, area, skills, pay/unit, dates, and state on the server. On job creation, persist a unique submission key per employer: retrying the same submission after a lost response returns the original job; reusing its key for different fields returns a conflict.

## 6. Git and private repository

The active GitHub CLI login was verified as **`X3r0Day`**. No local Git repository existed, and `X3r0Day/delhi4` did not resolve for that account during planning.

During the build, initialize `main`, set the **local** commit identity to `X3r0Day` with its GitHub-associated noreply email, and add ignore rules for local env files, Firebase credentials, tool state, and build artifacts before staging anything. Create the GitHub remote **private from the start**, with no initial push. Run the following as a fail-fast sequence after the first local commit:

```sh
set -e
test "$(gh api user --jq .login)" = X3r0Day
gh repo create X3r0Day/delhi4 --private --source=. --remote=origin
test "$(gh repo view X3r0Day/delhi4 --json visibility --jq .visibility)" = PRIVATE
git remote get-url origin
```

Confirm `origin` names `X3r0Day/delhi4` before `git push -u origin main`. If the name is already in use at execution time, inspect its owner, visibility, and history before attaching it. Grant Vercel access to this private repository only. The live site can be public while its source stays private.

**Requested commit schedule:** Monday, **2026-11-23**, Asia/Kolkata (`+05:30`). Set both Git author and committer timestamps to the listed time for each actual changeset. Each gap is 11–14 minutes.

| IST | Commit subject |
|---|---|
| 20:54 | `Lay out the web app and API around the launch plan` |
| 21:06 | `Add local trades, postal areas, and the two kinds of opening` |
| 21:19 | `Sign in by phone and keep the session in a cookie` |
| 21:30 | `Issue profile IDs and let workers choose when they are visible` |
| 21:44 | `Match local openings to the trades and areas a worker picked` |
| 21:56 | `Invite a worker and track the hire through to closure` |
| 22:07 | `Let people dictate and listen to jobs in Hindi or English` |
| 22:20 | `Check visibility, job history, and the no-microphone journey` |
| 22:34 | `Wire up Vercel and document the release checks` |

Verify both timestamps with `git log --reverse --format='%aI %cI %s'` before pushing.

## 7. Deployment and release checks

1. **Prove the deployment shape early.** Import the private repository into Vercel. Configure `apps/web` and `apps/api` as service roots; FastAPI registers routes including `/api` because [Vercel preserves that prefix](https://vercel.com/docs/services/routing). Services is currently beta: use the first preview to verify that a page, an API route, and a cookie round trip all work on one hostname.
2. **Isolate environments.** Use separate Firebase projects and databases or isolated Neon branches for staging and production. Preview builds must not inherit production credentials or real user data. Browser build variables are limited to Firebase's public configuration. Keep Firebase Admin credentials, the pooled `DATABASE_URL`, `CSRF_SECRET`, and exact allowed origins in server settings; keep the direct migration URL in the release job. Validate configuration at startup. Production must reject auth-emulator settings.
3. **Gate release on meaningful checks.** CI runs lint, type checking, a production web build, migrations against clean Postgres, API integration tests, and a two-user browser journey using the Firebase Auth Emulator. Cover repeated onboarding, revoked sessions, cross-account access, CSRF, ID collisions, competing assignments, locality ordering, type and deadline filters, availability expiry at local midnight, and a pause between shortlist display and invitation. Verify that a permanent placement cannot be marked as a completed shift.
4. **Promote deliberately.** Apply backward-compatible migrations once from a protected release job. Configure server-only speech credentials, budgets/usage alerts for speech and SMS, redacted error reporting, and Postgres backups. On the deployed staging origin, check OTP, audio recording/playback on Android Chrome and iOS Safari, and the full text journey with mic denied or the speech service offline. Check the Hindi flow at 360 px wide, on a throttled connection, and with keyboard navigation. Record how to roll back the app while retaining a compatible schema.
5. **Production sign-off:** Sign in with real SMS, retain IDs/history across sign-out, and verify the journeys below. A third account cannot read private contact details or earnings. The GitHub visibility check returns `PRIVATE`. No fabricated accounts, jobs, counters, or production test-number shortcuts.

### Evidence to show judges

- **Daily wage:** With two consenting accounts in a supported non-metro locality, the worker picks a trade and “Open today.” The employer dictates a short-term opening, checks the transcript, specifies a day rate and dates, and posts. The worker listens to the matched card in Hindi. The employer invites them, the worker accepts, and the employer assigns and completes the job. The worker's history gains exactly one completed job.
- **Permanent work and worker choice:** Post a permanent opening with monthly pay. A short-term-only worker should not match. Change their preference and check the match reason; pause availability and refresh the employer's shortlist. The worker disappears from discovery but can still apply themselves. Filling this vacancy records a placement, not wages or a completed shift.
- **Access without voice or a personal smartphone:** Receive the OTP on a basic phone and use a shared browser. Deny mic permission, finish the same form with controls, switch language, and sign out. A browser is required today; a call alone is a future milestone.

## 8. Future: one phone number, keypad-only access

The long-term promise is that someone with only a basic phone can **register, find and act on work, offer their availability, or hire someone by dialing a number**. The numbered menus below describe the future call experience; no number purchase, IVR provider, telephony webhook, or simulated dialer is part of the website build.

| Future call menu | Shared capability to build for the website now |
|---|---|
| First call: choose language and role; select trade and area; hear details; press a key to confirm | Localized catalogs, verified-actor registration, review/confirm, one public ID. Future callers must be able to enroll without ever visiting the site. |
| Worker: **1** hear nearby jobs and express interest; **2** open or pause availability; **3** hear invitations, work status, and record pay received for a completed job | Ranked, paginated matches with reasons; explicit availability setter; invitation responses, history, and reported earnings. |
| Employer: **1** post work; **2** invite a candidate or select an interested worker; **3** hear status, fill, complete, or cancel | Structured trade, locality, type, dates, pay and unit; candidate/invitation flow; validated job transitions. A keypad-only posting can derive its title from those choices without spelling a description. |
| Either role: hear my public ID, change language, or update work area; workers can also change trades and preferred opening types | The same profile and editable preferences as the dashboard, confirmed before saving. |

The future call adapter should read back choices, offer repeat/back/next, and require confirmation before a write. Give each displayed choice a temporary keypad number; do not ask callers to key in a UUID or public ID. Prove phone ownership without a browser (for example, a verified voice callback with a keypad challenge); caller ID alone is insufficient. Resolve the same internal profile and call the same domain services. Explicit state-setting, stable pagination, and duplicate-safe writes are useful on the website today and will also keep repeated keypresses from creating a second posting or hire.

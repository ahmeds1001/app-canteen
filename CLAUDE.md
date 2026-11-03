# OVAGRI Canteen App — instructions for Claude Code

Employees of OVAGRI Groupe reserve their canteen meal before midnight the day before; the kitchen cooks
reserved + 10 % buffer; a dedicated canteen phone scans a QR code per meal. Full specification:
**`docs/cahier-des-charges.md` (source of truth — read the relevant section before any change).**

## Stack

| Layer | Tech | Folder |
|---|---|---|
| Frontend (PWA) | React 18 + TypeScript + Vite, React Router, TanStack Query, react-i18next | `frontend/` |
| Backend (API) | Django 5.2 LTS + Django REST Framework + SimpleJWT | `backend/` |
| Database | Microsoft SQL Server 2019+ via `mssql-django` (ODBC Driver 18) | — |
| Scheduler | `python manage.py run_scheduler` (idempotent jobs, every minute) | `backend/apps/*/jobs.py` |

## Architecture (MVC, layered)

```
React (View)  ──HTTP/JSON──▶  DRF views (Controller)  ──▶  services.py (business rules)  ──▶  models.py (Model)
                                     │                                                 ▲
                                     └── serializers.py (input validation / output)    selectors.py (read queries)
```

Backend, one Django app per domain in `backend/apps/`: `core` (clock, settings, audit, permissions),
`accounts`, `menus`, `reservations`, `reports`. Inside each app:

- `models.py` — **Model**: tables, constraints, no business logic beyond invariants.
- `services.py` — **business rules** (the brain of the controller). Every FR rule lives here. Raise `DomainError` /
  `Conflict` / `NotAllowed` from `apps.core.exceptions` with a stable `code` (the frontend translates codes).
- `selectors.py` — read-only queries (lists, reports).
- `serializers.py` — validate input, shape output. No rules.
- `views.py` — **Controller**: thin. Validate → call ONE service/selector → serialize. No ORM writes in views.
- `jobs.py` — scheduled transitions (must be idempotent).
- `tests/` — Django `TestCase`s; freeze time with `apps.core.clock.frozen(...)`.

Frontend (`frontend/src/`) — the **View** layer:

- `api/types.ts` (API models) and `api/endpoints.ts` (one function per endpoint). Pages never call `fetch` directly.
- `hooks/` (auth, error messages), `components/ui` (primitives), `components/layout`, `pages/<role>/`.
- `i18n/fr.json`, `en.json` — every visible string. French is the default language.
- `styles/tokens.css` — brand tokens. **No hard-coded colours.** Logical CSS properties only (RTL later).

## Non-negotiable rules

1. **Time:** never call `timezone.now()` in business code — use `apps.core.clock.now()/today()` (tests freeze it).
   Company time zone: `Africa/Tunis`. Day rules live in `apps/menus/rules.py`.
2. **Concurrency:** state changes are conditional updates (`filter(status=X).update(...)`) or unique constraints,
   so double taps and parallel scans are safe. Keep reserve / cancel / scan / finalize / mark-paid idempotent.
3. **Audit:** every sensitive action calls `apps.core.audit.record(...)`. The audit log is append-only.
4. **Data is never deleted** (company decision): no hard deletes of users, reservations or audit rows.
5. **Settings** (cutoff, service window, buffer 10 %, payment, weekdays…) come from `CanteenSettings.load()`,
   never from constants.
6. **Security:** secrets only in `.env`; OTP and reset tokens stored hashed; QR payloads signed; role checks with
   `apps.core.permissions`.
7. **Spec first:** if a request conflicts with `docs/cahier-des-charges.md`, ask before coding. When a decision
   changes, update the spec too.

## Commands

```bash
# Backend (from backend/)
python -m venv .venv && .venv\Scripts\activate        # Windows (source .venv/bin/activate on Linux/macOS)
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver                            # http://localhost:8000/admin, API under /api/v1/
python manage.py run_scheduler                        # scheduled jobs (separate terminal)
python manage.py test --settings=config.settings.test # fast tests on SQLite in memory
ruff check .

# Frontend (from frontend/)
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
npm run typecheck
npm run build
```

Local DB without SQL Server: set `DB_ENGINE=sqlite` in `.env` (development only — production is SQL Server).

## Agents (`.claude/agents/`)

**First-time setup:** the agent files are shipped in `setup/claude-agents/`. If `.claude/agents/` is empty, copy
them there (`powershell -ExecutionPolicy Bypass -File setup\install-agents.ps1`, or ask Claude Code to do it), then
restart Claude Code. `setup/claude-agents/` stays as the versioned source; keep both in sync when editing an agent.

Adapted from oh-my-claudecode. Suggested flow for a backlog item:

1. **planner** → turns a backlog item into a plan in `docs/plans/` (cites FR IDs). **critic** / **architect** review it.
2. **executor** implements one plan step at a time; **designer** for any screen (follows `docs/design/brand.md`).
3. **test-engineer** writes/extends tests; **verifier** runs tests, typecheck and build and checks acceptance criteria.
4. **code-reviewer** + **security-reviewer** before merging; **git-master** for clean atomic commits.
5. **debugger** for failures, **explore** for finding code, **writer** for docs.

## Definition of done

- Behaviour matches the cited FR / business rule; spec updated if a decision changed.
- Backend tests pass (`manage.py test --settings=config.settings.test`), `ruff check .` clean.
- `npm run typecheck` and `npm run build` pass; new strings exist in **both** fr.json and en.json.
- New sensitive actions are audited; new time logic uses `clock`; no hard-coded colours.
- `docs/plans/backlog.md` updated (item ticked or moved).

## Working notes (kept up to date between sessions)

### Where we are (3 Nov 2026)
Everything is committed and pushed. Built and tested (118 backend tests): registration + HR approval with the
matricule typed by HR, dish library + planner, **two menus per day** (FR-42), reservations, **prepaid balance** —
the only way to pay, no counter payment (FR-43, `apps/wallet`), finalization per menu at 10:00, signed QR + scanner
showing the menu to serve, **day lists** (FR-44), **attendance per employee per month** ("Rapports", FR-22),
notifications in-app + push with **"handled for everyone"** (`Notification.resolved_at`), roles set by the admin.
French spec as PDF: `docs/cahier-des-charges.pdf`; test guide: `docs/guide-test-semaine.md` (+ PDF).

### Next steps (agreed order — confirm with the user before starting)
1. ~~Quick fixes before real use~~ — done 3 Nov 2026 (127 tests): account emails leave via `transaction.on_commit`
   (tests use `captureOnCommitCallbacks(execute=True)` to see `mail.outbox`); SQLite `timeout: 20`; no delete in
   the Django admin for app data; refresh-token blacklist (`accounts.services.end_sessions`, rule
   `active_account_rule`), and the frontend shares one refresh call (`api/client.ts`) since a refresh token works once.
2. Run the test suite and a manual pass on **SQL Server** (filtered unique constraints, JSON fields, decimals).
3. Decide with management: balance of an employee who leaves; who may collect cash; daily cash check
   (→ cash reconciliation report: top-ups per cashier per day); backup person for finalization; leftover plates.
4. Deploy on the company server (Docker, SQL Server, HTTPS, backups + restore test), load test (200 users), pilot.
5. Then: no-show warning after 3 per month, management trend charts (FR-23), chef live count (FR-21), offline scans.

### How the user works
- Writes in English (sometimes French); the **app, PDFs and user guides are in French**. Answers short and clear.
- After each change: tests + typecheck + build, then **check in the browser**; the user then says "commit and push".
  Commit only when asked; push to `origin main`. Repo: `github.com/ahmeds1001/app-canteen`, local git identity
  `ahmeds1001` — **never use or touch the user's other GitHub account (sigma.garay1)**.
- Ask before changing a business rule (spec first); several short questions at once are welcome.
- Deletes in the Django admin: blocked for all app data on 3 Nov 2026 (was "not now" on 2026-10-26).

### Windows environment (this PC)
- Shells: PowerShell 5.1 (no `&&`; use `;` / `if ($?)`), and Git Bash. Use **`npm.cmd`** in PowerShell (the
  execution policy blocks `npm.ps1`). Git needs PATH refreshed in PowerShell:
  `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`.
  `git push` writes to stderr, so PowerShell may report exit 255 even when the push succeeded.
- PowerShell piping into `manage.py shell` adds a BOM: use `manage.py shell -c "..."` from Git Bash instead.
- Local DB is SQLite (`DB_ENGINE=sqlite` in `.env`, file `backend/db.sqlite3`). Data is never deleted, even here.
- The user's own servers usually run in cmd windows; if they freeze, clicking in a cmd window pauses it (Windows
  QuickEdit) — press Esc.

### Test tools
- Test clock (DEBUG only): `python manage.py dev_clock set 2026-11-25 08:30` / `dev_clock reset` (shared by API and
  scheduler, file `backend/.dev_clock`; the clock keeps running from the set time). Moving it back undoes nothing.
- Test week: `python manage.py demo_week [--monday YYYY-MM-DD]` — adds a Monday–Saturday week (two-menu days,
  balances, history) without deleting anything, then sets the clock to that Tuesday 20:30. On this PC the weeks of
  9 and 23 Nov are built and the week of 16 Nov is half-built (an old bug, kept); use a later Monday for a new one.
- Test accounts: `admin@`, `hr@`, `chef@`, `management@`, `scanner@`, `employee@ovagri.test` + generated employees;
  password = `DEV_SEED_PASSWORD` in `.env` (never write it in files or chat).
- Pixel 6 Pro over wireless debugging: `adb pair` / `adb connect`, then `adb reverse tcp:5173 tcp:5173` and open
  `http://localhost:5173` in Chrome on the phone (camera needs localhost). Redo `adb reverse` after reconnecting.
  `npm run dev:lan` exposes Vite on the Wi-Fi (no camera there: phone shows the QR, PC scans).
- PDFs are printed from HTML with headless Edge (`msedge --headless --print-to-pdf`, `--virtual-time-budget=20000`
  for the mermaid diagrams); check pages by rendering them (pypdfium2) before sending.

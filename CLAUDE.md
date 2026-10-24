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

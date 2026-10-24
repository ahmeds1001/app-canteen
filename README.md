# Cantine OVAGRI

Web app (installable on the phone) for reserving canteen meals at OVAGRI Groupe: employees reserve before
midnight the day before, the kitchen cooks reserved + 10 %, and a canteen phone scans a QR code per meal.

- Specification: [`docs/cahier-des-charges.md`](docs/cahier-des-charges.md)
- Brand guide: [`docs/design/brand.md`](docs/design/brand.md)
- What's next: [`docs/plans/backlog.md`](docs/plans/backlog.md)
- Working with Claude Code and the agents: [`CLAUDE.md`](CLAUDE.md)

## Structure

```
backend/            Django 5.2 + DRF API (SQL Server)
  config/           settings (base, dev, test, prod), urls
  apps/core/        clock, settings singleton, audit log, permissions, emails, scheduler command
  apps/accounts/    users, OTP, HR approval, password reset
  apps/menus/       dish library, menus, finalization, day rules
  apps/reservations/ reservations, QR scan, payment, no-shows
  apps/reports/     daily and attendance reports
  templates/emails/ email texts
frontend/           React + TypeScript + Vite PWA
  src/api/          API types and endpoint functions
  src/pages/        screens per role (auth, employee, chef, management, hr, scanner)
  src/components/   UI primitives and layouts
  src/i18n/         fr.json, en.json
  src/styles/       brand tokens (from the logo)
docs/               spec, brand guide, plans
.claude/agents/     Claude Code agents (installed from setup/claude-agents)
setup/              agent sources + install script
```

## Run locally (Windows)

Prerequisites: Python 3.12+, Node 20+, and either SQL Server with
[ODBC Driver 18](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) or `DB_ENGINE=sqlite` for a quick try.

```powershell
copy .env.example .env          # then edit it

cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements\dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# second terminal
cd frontend
npm install
npm run dev                     # open http://localhost:5173
```

In development, emails (OTP codes, reset links) are printed in the backend terminal.

## Tests

```powershell
cd backend
python manage.py test --settings=config.settings.test
cd ..\frontend
npm run typecheck
npm run build
```

## Deploy (company server)

`docker compose up -d --build` starts the API, the scheduler and the web front (port 8080). Put it behind the
company reverse proxy on its own subdomain with HTTPS. It uses its own SQL Server database and login, with no
rights on the ERP.

Agents (`setup/claude-agents/` → `.claude/agents/`, see CLAUDE.md) are adapted from [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) (MIT).

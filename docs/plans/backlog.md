# Backlog

Ordered by priority. Each item cites the spec (`docs/cahier-des-charges.md`). Use the **planner** agent to turn an
item into a plan file in this folder, then the **executor** to build it.

## Done in the initial scaffold

- [x] Repo structure, settings per environment, SQL Server config, Docker files
- [x] Models for every table in spec §6.1 + migrations
- [x] Registration with email OTP, login, HR approve/reject/suspend, password reset by link and by HR (FR-01–06, FR-39, FR-40) — API + tests
- [x] Roster CSV import (FR-37) — API
- [x] Dish library + menu building with snapshot, publishing deadline, placeholder menu job (FR-07, FR-29–31, FR-38) — API + tests
- [x] Finalization with 10 % buffer and auto-finalization (FR-24–27) — API + tests
- [x] Reservation / cancel with midnight cutoff, unique active reservation per day (FR-11–13) — API + tests
- [x] QR scan with atomic claim, service window, offline timestamp rule, manual check-in, mark paid (FR-16–20, FR-34–35) — API + tests
- [x] No-show job, daily and attendance reports with CSV export (FR-21–23, FR-36) — API
- [x] Frontend: brand tokens, auth screens (register, OTP, login, pending, forgot/reset/forced change), employee menus + reserve/cancel, my reservations with QR, scanner screen

## Sprint 1 — finish the core loop

- [x] **Chef planner screen** (FR-07, FR-09, FR-10, FR-38): week view, pick dishes from the library (or create one on the spot), publish a day or the whole week, duplicate another day's menu, close a day.
- [x] **Dish library screen** (FR-29–31): list with search/category filter, last served date, create/edit/archive, photo upload.
- [x] **Management finalization screen** (FR-24–28): reserved count, proposed count (10 %), adjust, confirm, change until service starts. (FR-28 chef notification is part of Notifications below.)
- [x] **HR accounts screen** (FR-04–06, FR-37, FR-40): pending list with roster match flag, approve/reject (reason), bulk approve, suspend/reactivate/deactivate, reset password (show temporary password once), CSV import.
- [ ] **Notifications** (spec §8): menu announced, placeholder published, placeholder empty at cutoff, day finalized → chef, menu changed / day switched to paid → employees, finalization reminder, missing-menu reminder, day closed → employees whose reservation was cancelled.
- [x] Close day → cancel its reservations (`menus/services.close_day`). Notifying the employees is part of Notifications.
- [ ] Refresh-token blacklist so a password change ends other sessions (FR-39) — `rest_framework_simplejwt.token_blacklist`.

## Sprint 2 — reliability and reports

- [ ] Scanner offline queue: store scans with their timestamp when the network fails, resend later (rule "Offline scan sync").
- [ ] Management and HR report screens with charts and CSV export (FR-21–23, FR-36).
- [ ] No-show warning email after 3 per calendar month, only after the grace month (business rule "No-show consequences").
- [ ] Admin: settings screen is the Django admin for now; check every setting is editable and audited (`setting_change`).
- [ ] Evening reminder at 20:00 for employees without a reservation (spec §8, could have).

## Before the pilot

- [ ] Deploy on the company server (own containers, own DB and login, subdomain + HTTPS, isolated from the ERP).
- [ ] Daily backups off the server + one restore test.
- [ ] Load test: 200 users reserving in the last minutes before midnight.
- [ ] One-page employee guide, short trainings (HR, chef, management, scanner).

## Open questions (see also open-questions.md)

- Which weekdays is the canteen open? The code assumes **Monday–Friday** (`CanteenSettings.service_weekdays`).
- Backup person for finalization; strategy for leftover plates (after the pilot).
- SVG logo and square app icon from the communication team.

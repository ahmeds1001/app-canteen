# Plan — In-app and push notifications (spec §8, FR-28)

Status: **built** (2026-10-25). Approved 2026-10-24 with 08:00 / 08:00 / 20:00.

Differences from the proposal below, decided while building:
- Notification texts are built on the server (`apps/notifications/messages.py`, fr/en) for both the in-app list
  and the push, instead of being translated in the app. One source of text; the list follows the app language.
- A notification is marked read when tapped, or with "Tout marquer comme lu" (not just by opening the list).
- The bell is hidden for the scanner role (it receives no notifications).

Decision (user, 2026-10-24): every non-account message is an **in-app notification + phone push**, no email.
Account messages (OTP code, reset link, password changed, approved, rejected) stay emails. Spec §8 updated.

## What the user sees

- **Bell** in the app bar with the unread count (polled every 60 s). Tapping it opens **"Notifications"**: newest
  first, unread in bold, each with a link to the right screen (e.g. "Final count: 47 plates" → chef planner).
  Opening the list marks them read; "Tout marquer comme lu" too.
- **"Activer les notifications sur ce téléphone"** button on the notifications page. The browser asks for
  permission; after that, messages also appear on the lock screen, even with the app closed. One subscription per
  phone/browser; a user can have several. "Désactiver" turns it off for that phone.
- Texts are translated in the app (fr/en) from a stable `kind` + parameters, like error codes. Push texts are built
  on the server in the user's language (`preferred_language`, default French).

## Messages built in this plan

| # | kind | Trigger (where) | Recipients | Text (fr, short) |
|---|---|---|---|---|
| 1 | `accounts_pending` | email verified → status pending_hr (`accounts.services.verify_otp`) | HR | "Nouveau compte à valider : {name} (sur la liste / hors liste)" |
| 2 | `menu_changed` | dishes changed on a **published** day that has reservations (`menus.services.set_items`) | employees who reserved | "Le menu du {date} a changé. Vous pouvez annuler avant minuit la veille." |
| 3 | `menu_announced` | first dishes added to a placeholder (`set_items`, replaces the TODO) | employees who reserved | "Le menu du {date} est annoncé : {dishes}." |
| 4 | `price_changed` | paid flag / price changed with reservations (`set_payment`) | employees who reserved | "Le repas du {date} est maintenant payant : {price} TND." / "…gratuit." |
| 5 | `day_closed` | day closed (`close_day`) | employees whose reservation was cancelled | "La cantine est fermée le {date} ({reason}). Votre réservation est annulée." |
| 6 | `placeholder_published` | scheduler publishes a placeholder (`jobs.publish_placeholders`) | chef + management | "Le {date} est ouvert en « Menu à venir ». Ajoutez les plats avant la clôture." |
| 7 | `placeholder_empty_at_cutoff` | menu locks while still empty and has reservations (`jobs.lock_menus`) | chef + management | "Le {date} a {n} réservations mais aucun plat." |
| 8 | `finalization_reminder` | daily job at `finalization_reminder_time` (default 08:00) for today's locked, not yet finalized day | management | "{n} réservations pour le {date}. Confirmez le nombre d'assiettes avant {time}." |
| 9 | `day_finalized` | `menus.services.finalize` (manual and auto) — FR-28 | chef | "Le {date} : {plates} assiettes à préparer ({reserved} réservations + {buffer})." |
| 10 | `menu_missing` | new daily job at `menu_missing_reminder_time` (default 08:00) | chef | "Menus à publier : {dates}." (only if some days in the next D-2 window have no published menu) |
| 11 | `reservation_reminder` | new daily job at `evening_reminder_time` (default 20:00), only if tomorrow is open for reservation (published, incl. "Menu à venir") | every active account that eats (employee, HR, chef, management; not scanner/admin) **without an active reservation for tomorrow**, and who has not turned the reminder off | "Vous n'avez pas réservé pour demain ({date}) : {dishes}. Réservez avant minuit." Tapping it opens the menus with a "Réserver" button |

**Evening reminder opt-out:** some people never eat at the canteen. The notifications page has a switch
"Rappel du soir" (on by default) stored on the user (`evening_reminder` boolean). Turning it off stops message 11
only.

Already planned elsewhere, built with the same mechanism later: no-show warning (Sprint 2), unpaid meals
(payment is off). "Reservation confirmed" is not sent (decided in §8).

## Backend (new app `apps/notifications`)

- `models.py`
  - `Notification`: user, kind, params (JSON), link, created_at, read_at, pushed_at, **dedupe_key**.
    Unique (user, kind, dedupe_key) so jobs that run every minute never notify twice (rule 2: idempotent).
    Never deleted (rule 4).
  - `PushSubscription`: user, endpoint (unique), p256dh, auth, user_agent, created_at, revoked_at
    (revoked instead of deleted; revoked automatically when the push service answers 404/410).
- `services.py`: `notify(users, kind, params, link, dedupe_key)` creates the rows (bulk, ignore duplicates);
  `mark_read`, `mark_all_read`, `subscribe`, `unsubscribe`. Business code calls `notify(...)` only.
- `push.py`: Web Push sender using **pywebpush** (new dependency) with **VAPID keys from `.env`**
  (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`; rule 6). A command `manage.py generate_vapid_keys`
  prints a new pair.
- `jobs.py`: `send_pending_pushes` (every scheduler tick: rows with `pushed_at` NULL, max age 1 day; marks
  `pushed_at` even if the user has no subscription), `menu_missing_reminder` and `evening_reservation_reminder`
  (once a day each: the dedupe key is the date, so a tick that runs late or twice sends nothing new). Pushes therefore go
  out within a minute; requests never wait for the push service.
- API (`/api/v1/notifications/`): list (latest 50 + unread count), `POST {id}/read`, `POST read-all`;
  `GET push/key` (public VAPID key), `POST push/subscribe`, `POST push/unsubscribe`. Own notifications only.
- `CanteenSettings.menu_missing_reminder_time` (default 08:00), `finalization_reminder_time` (default 08:00) and
  `evening_reminder_time` (default 20:00) — rule 5, editable in the admin.
- `User.evening_reminder` (boolean, default true) + `PATCH /api/v1/notifications/preferences`.
- Audit: subscribing/unsubscribing is not a sensitive action; no audit rows. Notifications themselves are the record.

## Frontend

- `api/types.ts`, `api/endpoints.ts`: `Notification`, `notificationApi`, `pushApi`.
- `components/layout/NotificationBell.tsx` in the app bar (all roles, also the scanner phone? **no** — the
  scanner role gets no notifications, so no bell there).
- `pages/NotificationsPage.tsx` (`/notifications`): list, mark all read, enable/disable push on this device.
- Service worker: vite-plugin-pwa keeps `generateSW`; a small `public/push-sw.js` is added with
  `workbox.importScripts` to show the push and open the link when tapped.
- `i18n/fr.json`, `en.json`: one string per kind.

## Tests

- Backend: each trigger creates the right rows for the right users (and none for others); jobs are idempotent
  (run twice → one notification); `send_pending_pushes` with the push call mocked (success, 410 → subscription
  revoked); API returns only the user's own notifications.
- Manual on the Pixel (localhost through adb counts as HTTPS-like): enable push, close Chrome, trigger "day
  finalized" with the test clock → notification on the lock screen.

## Not in this plan

- Native mobile app; SMS; email digests.
- Push on iPhone before the app is on the company server (needs HTTPS and home-screen install).

## Times (proposed, editable later in the admin settings)

- "Menus à publier" for the chef: **08:00**.
- Finalization reminder for management: **08:00** on day D (nobody acts at midnight; auto-finalization at 12:00
  stays the safety net).
- Evening reservation reminder: **20:00** the day before (4 hours before the midnight cutoff).

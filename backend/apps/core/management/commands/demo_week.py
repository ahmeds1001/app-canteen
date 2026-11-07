"""Development only: add a realistic test week (Monday to Saturday) to the current database.

    python manage.py demo_week                      # week of Monday 30 Nov 2026 (the one the guide describes)
    python manage.py demo_week --monday 2026-12-07  # another week, when that one is already built

Nothing is deleted or overwritten: existing accounts and dishes are reused, missing ones are added, and the
week is built only if none of its days has a menu yet (running it twice does nothing the second time).
So that the guide reads the same on any week, the test employee starts the week with exactly 15 TND and two
sign-ups wait for HR (new ones are added when earlier test weeks already dealt with them).

Every step goes through the real services under a frozen clock, and the scheduler runs at each step, so locks,
finalizations, scans, no-shows, notifications, balances and the audit log are what the app itself would have
produced. At the end the test clock is set to the Tuesday of that week at 20:30.
The test scenarios: docs/guide-test-semaine.md.
"""
import os
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import services as accounts
from apps.accounts.models import User
from apps.core import clock
from apps.core.exceptions import DomainError
from apps.core.management.commands.run_scheduler import tick
from apps.core.models import CanteenSettings
from apps.menus import services as menus
from apps.menus.models import Dish, Menu
from apps.notifications import events as notification_events
from apps.reservations import services as reservations
from apps.reservations.models import Reservation
from apps.wallet import services as wallet

TZ = ZoneInfo(settings.TIME_ZONE)
DEFAULT_MONDAY = date(2026, 11, 30)  # the week docs/guide-test-semaine.md describes
PERSONA = "employee@ovagri.test"  # the account the guide uses to test as an employee
PERSONA_START = Decimal("15.000")  # balance before the week: 3 meals (Mon, Tue, Thu) + Wednesday; Friday is short
MEAL_PRICE = Decimal("3.000")
FRIDAY_PRICE = Decimal("3.500")

STAFF = {  # email: (first name, last name, role, matricule)
    "admin@ovagri.test": ("Admin", "Test", User.Role.ADMIN, "ADM-001"),
    PERSONA: ("Employe", "Test", User.Role.EMPLOYEE, "EMP-001"),
    "hr@ovagri.test": ("RH", "Test", User.Role.HR, "RH-001"),
    "chef@ovagri.test": ("Chef", "Test", User.Role.CHEF, "CHEF-001"),
    "scanner@ovagri.test": ("Scanner", "Test", User.Role.SCANNER, "SCAN-001"),
    "cashier@ovagri.test": ("Caisse", "Test", User.Role.CASHIER, "CAIS-001"),  # FR-47: records the top-ups
    "management@ovagri.test": ("Direction", "Test", User.Role.MANAGEMENT, "DIR-001"),
}

EMPLOYEES = [  # first name, last name, department
    ("Mohamed", "Ben Ali", "Production"), ("Fatma", "Trabelsi", "Qualité"), ("Hichem", "Gharbi", "Logistique"),
    ("Salma", "Jaziri", "Commercial"), ("Walid", "Hammami", "Maintenance"), ("Rim", "Bouaziz", "Production"),
    ("Anis", "Chaabane", "Production"), ("Nour", "Mejri", "Administration"), ("Khaled", "Ayari", "Logistique"),
    ("Asma", "Khelifi", "Qualité"), ("Bilel", "Saidi", "Production"), ("Meriem", "Ferchichi", "Commercial"),
    ("Sofiene", "Dridi", "Maintenance"), ("Ons", "Mansouri", "Administration"), ("Tarek", "Baccouche", "Production"),
    ("Houda", "Zouari", "Qualité"), ("Amine", "Kefi", "Logistique"), ("Leila", "Ben Amor", "Production"),
    ("Yassine", "Jebali", "Production"), ("Ines", "Sassi", "Commercial"),
]
SUSPENDED = ("Riadh", "Hamdi", "Production")
PENDING = [("Sarra", "Bouzid", "Qualité"), ("Omar", "Tlili", "Production")]

DISHES = {  # name: (category, allergens, description)
    "Chorba frik": ("starter", "gluten", "Soupe d'orge vert à l'agneau"),
    "Salade mechouia": ("starter", "", "Poivrons et tomates grillés, thon, œuf"),
    "Brik à l'œuf": ("starter", "gluten, œuf", ""),
    "Salade tunisienne": ("starter", "", "Tomate, concombre, oignon, olives"),
    "Couscous au poulet": ("main", "gluten", ""),
    "Riz djerbien": ("main", "", "Riz vapeur aux légumes et au poulet"),
    "Pâtes au thon": ("main", "gluten, poisson", ""),
    "Mloukhia au bœuf": ("main", "", ""),
    "Couscous au poisson": ("main", "gluten, poisson", ""),
    "Escalope panée et frites": ("main", "gluten, œuf", ""),
    "Ojja merguez": ("main", "œuf", ""),
    "Kafteji": ("main", "œuf", "Légumes frits, œuf, sauce piquante"),
    "Poisson grillé": ("main", "poisson", ""),
    "Fruit de saison": ("dessert", "", ""),
    "Yaourt nature": ("dessert", "lait", ""),
    "Crème au chocolat": ("dessert", "lait", ""),
    "Makroud": ("dessert", "gluten", "Gâteau de semoule aux dattes"),
}
# Day offset from Monday → menu 1, and menu 2 when the day offers a choice (decided 2026-11-03).
MENUS = {
    0: (["Chorba frik", "Couscous au poulet", "Fruit de saison"], []),
    1: (["Salade mechouia", "Riz djerbien", "Yaourt nature"], ["Salade mechouia", "Kafteji", "Yaourt nature"]),
    2: (["Brik à l'œuf", "Pâtes au thon", "Crème au chocolat"], ["Brik à l'œuf", "Ojja merguez", "Crème au chocolat"]),
    3: (["Salade tunisienne", "Mloukhia au bœuf", "Fruit de saison"],
        ["Salade tunisienne", "Poisson grillé", "Fruit de saison"]),
    4: (["Chorba frik", "Couscous au poisson", "Makroud"], ["Chorba frik", "Escalope panée et frites", "Makroud"]),
    5: (["Salade mechouia", "Escalope panée et frites", "Yaourt nature"], []),  # left as a draft for the chef
}
SHARE_RESERVING = {0: 0.8, 1: 0.75, 2: 0.7, 3: 0.55, 4: 0.35}
PERSONA_DAYS = {0: (1, "no_show"), 1: (2, "served"), 3: (1, "reserved")}  # offset: (menu, outcome)


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=TZ)


class Command(BaseCommand):
    help = "Add a test week to the current database and set the test clock (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--monday", type=date.fromisoformat, default=DEFAULT_MONDAY,
                            help="Monday of the week to build (YYYY-MM-DD). Default: 2026-11-30.")

    def handle(self, *args, monday: date, **options):
        if not settings.DEBUG:
            raise CommandError("demo_week is only available when DEBUG is on.")
        if monday.weekday() != 0:
            raise CommandError(f"{monday} is not a Monday.")
        password = os.environ.get("DEV_SEED_PASSWORD")
        if not password:
            raise CommandError("Set DEV_SEED_PASSWORD in .env: it becomes the password of the accounts created.")
        self.days = [monday + timedelta(days=n) for n in range(6)]
        self.start = at(self.days[1], 20, 30)  # Tuesday evening: Wednesday can still be reserved
        self.rng = random.Random(monday.toordinal())
        self.events: list[tuple[datetime, int, object]] = []

        users = self._users(password)
        dishes = self._dishes(users["chef"], at(monday - timedelta(days=5), 15))
        if Menu.objects.filter(date__range=(self.days[0], self.days[-1])).exists():
            self.stdout.write(f"The week of {monday:%d/%m} already has menus: nothing more to build. "
                              "Use --monday with a later Monday for a new week.")
        else:
            with transaction.atomic():  # all or nothing: a failure never leaves a half-built week
                self._plan_week(users, dishes)
                self._run()
        call_command("dev_clock", "set", self.start.strftime("%Y-%m-%d"), self.start.strftime("%H:%M"),
                     stdout=self.stdout)
        self._summary()

    # --- People and dishes (reused when they exist) ----------------------------------------
    def _user(self, email, first, last, password, **fields) -> User:
        user = User.objects.filter(work_email=email).first()
        if user is None:
            user = User.objects.create_user(email, password, first_name=first, last_name=last, **fields)
            self.stdout.write(f"  + {email}")
        return user

    def _users(self, password) -> dict:
        found = {}
        for email, (first, last, role, number) in STAFF.items():
            admin = role == User.Role.ADMIN
            found[role if email != PERSONA else "persona"] = self._user(
                email, first, last, password, role=role, status=User.Status.ACTIVE, is_staff=admin,
                is_superuser=admin, employee_number=number, department="Test",
            )
        self.employees = [
            self._user(f"{first.lower()}.{last.lower().replace(' ', '')}@ovagri.test", first, last, password,
                       department=dept, status=User.Status.ACTIVE, employee_number=f"EMP-{2001 + i}")
            for i, (first, last, dept) in enumerate(EMPLOYEES)
        ]
        # Accounts that already existed (Ahmed, Ines, Yasmine…) eat too.
        self.employees += list(User.objects.filter(role=User.Role.EMPLOYEE, status=User.Status.ACTIVE)
                               .exclude(work_email=PERSONA).exclude(pk__in=[u.pk for u in self.employees]))
        first, last, dept = SUSPENDED
        self.suspended = self._user(f"{first.lower()}.{last.lower()}@ovagri.test", first, last, password,
                                    department=dept, status=User.Status.ACTIVE, employee_number="EMP-2099")
        # He is suspended on Monday: he never reserves (a tester may have reactivated him the week before).
        self.employees = [u for u in self.employees if u.pk != self.suspended.pk]
        self.pending = []
        for first, last, dept in PENDING:
            email = f"{first.lower()}.{last.lower()}@ovagri.test"
            user = User.objects.filter(work_email=email).first()
            if user is not None and user.status != User.Status.PENDING_HR:
                # Approved or refused during an earlier test week: a new sign-up with the same name waits.
                email = f"{first.lower()}.{last.lower()}.{self.days[0]:%Y%m%d}@ovagri.test"
            self.pending.append(self._user(email, first, last, password, department=dept,
                                           status=User.Status.PENDING_HR))
        return found

    def _dishes(self, chef, when) -> dict:
        dishes = {}
        for name, (category, allergens, description) in DISHES.items():
            dish = Dish.objects.filter(name=name, is_archived=False).first()
            if dish is None:
                with clock.frozen(when):
                    dish = menus.create_dish(by=chef, name=name, category=category, allergens=allergens,
                                             description=description)
            dishes[name] = dish
        return dishes

    # --- The week, as a list of timed events ------------------------------------------------
    def _on(self, when: datetime, fn):
        self.events.append((when, len(self.events), fn))

    def _plan_week(self, users, dishes):
        chef, hr, management, scanner, persona = (users[k] for k in ("chef", "hr", "management", "scanner", "persona"))
        cashier = users["cashier"]  # top-ups go through the cashier since 2026-11-05 (FR-47)
        mon, tue, wed, thu, fri, sat = self.days
        cfg = CanteenSettings.load()
        # Every meal is paid from the prepaid balance (decided 2026-11-03): 3.000 TND by default.
        cfg.payment_enabled, cfg.meal_paid_default, cfg.meal_price_default = True, True, MEAL_PRICE
        cfg.save()

        # The scheduler runs at the key moments of every day, which also settles older test days.
        day = mon - timedelta(days=4)
        while at(day, 0, 1) < self.start:
            for hh, mm in ((0, 1), (8, 0), (10, 0), (15, 1), (20, 0)):
                if at(day, hh, mm) < self.start:
                    self._on(at(day, hh, mm), lambda: None)
            day += timedelta(days=1)

        # Cash given at the canteen before the week: everyone tops up their balance.
        top_ups = mon - timedelta(days=4)
        for user in self.employees:
            amount = Decimal(self.rng.choice([20, 30, 40, 50]))
            self._on(at(top_ups, 9, self.rng.randint(0, 50)), lambda u=user, a=amount: wallet.top_up(u, a, by=cashier))
        self._on(at(top_ups, 12), lambda: self._set_persona_balance(persona, management))

        # Chef: Mon–Wed published Thursday before, Thu–Fri on Friday, Saturday still a draft on Tuesday.
        def build(day, publish=True):
            ids1, ids2 = ([dishes[n].pk for n in names] for names in MENUS[(day - mon).days])

            def run():
                menu = menus.get_or_create_menu(day, by=chef)
                menus.set_items(menu, ids1, dish_ids_2=ids2, by=chef)
                if publish:
                    menus.publish(menu, by=chef)
            return run

        for day in (mon, tue, wed):
            self._on(at(mon - timedelta(days=4), 9), build(day))
        for day in (thu, fri):
            self._on(at(mon - timedelta(days=3), 9), build(day))
        self._on(at(tue, 10), build(sat, publish=False))

        # Management sets Friday's price before anyone reserves it (one price for both menus).
        self._on(at(mon, 7, 30), lambda: menus.set_payment(Menu.objects.get(date=fri), is_paid=True,
                                                            price=FRIDAY_PRICE, by=management))

        # HR suspends one employee; two new sign-ups wait for HR on Tuesday evening.
        if self.suspended.status == User.Status.ACTIVE:  # already suspended by an earlier test week
            self._on(at(mon, 11), lambda: accounts.change_status(self.suspended, "suspend", by=hr))
        for i, user in enumerate(self.pending):
            self._on(at(tue, 18, 10 + 40 * i), lambda user=user: notification_events.account_pending(user))

        # Reservations (and a few cancellations) between D-3 and the evening before, never after the start.
        for offset, share in SHARE_RESERVING.items():
            day = self.days[offset]
            opens = max(at(day - timedelta(days=3), 8), at(mon - timedelta(days=3), 10))
            closes = min(at(day - timedelta(days=1), 22, 30), self.start - timedelta(minutes=10))
            two = bool(MENUS[offset][1])
            for user in self.employees:
                if self.rng.random() < share:
                    choice = 2 if two and self.rng.random() < 0.4 else 1
                    self._reserve(user, day, choice, self._between(opens, closes), closes)
            if offset in PERSONA_DAYS:
                choice = PERSONA_DAYS[offset][0]
                self._reserve(persona, day, choice, self._between(opens, closes), closes, may_cancel=False)

        # Service days already past: Monday auto-finalized at 10:00, Tuesday confirmed by management at 09:20.
        self._on(at(tue, 9, 20), lambda: self._finalize(tue, management))
        for day in (mon, tue):
            self._on(at(day, 11, 59), lambda day=day: self._plan_service(day, scanner, persona))

    def _set_persona_balance(self, persona, management):
        """The test employee starts every test week with exactly PERSONA_START, whatever earlier weeks left:
        a top-up of the difference, or a management correction when there is more (dev data only)."""
        persona.refresh_from_db()
        gap = PERSONA_START - persona.balance
        if gap > 0:
            wallet.top_up(persona, gap, by=management)  # may be under the cashier's minimum (FR-48)
        elif gap < 0:
            wallet.correct(persona, gap, by=management, reason="Semaine de test : solde remis à 15 TND")

    def _between(self, start: datetime, end: datetime) -> datetime:
        minutes = int((end - start).total_seconds() // 60)
        return start + timedelta(minutes=self.rng.randint(0, max(minutes, 0)))

    def _reserve(self, user, day, choice, when, closes, may_cancel=True):
        def run():
            menu = Menu.objects.get(date=day)
            try:
                reservation = reservations.reserve(user, menu, choice=choice)
            except DomainError:  # balance used up: this employee simply does not reserve that day
                return
            if may_cancel and self.rng.random() < 0.08:
                self._on(self._between(when + timedelta(minutes=5), closes),
                         lambda: reservations.cancel(reservation, by=user))
        self._on(when, run)

    def _finalize(self, day, management):
        menu = Menu.objects.get(date=day)
        proposal = menus.proposed_plate_count(menu)
        plates = {c["choice"]: c["proposed"] + (1 if c["choice"] == 1 else 0) for c in proposal["choices"]}
        menus.finalize(menu, plates=plates, by=management)

    def _plan_service(self, day, scanner, persona):
        """Called at 11:59: schedule the check-ins of the day's reservations between 12:05 and 14:25."""
        offset = (day - self.days[0]).days
        for reservation in Reservation.objects.filter(date=day, status=Reservation.Status.RESERVED):
            outcome = PERSONA_DAYS[offset][1] if reservation.user_id == persona.pk else None
            if outcome == "no_show" or (outcome is None and self.rng.random() > 0.88):
                continue  # becomes a no-show at 15:00 (the meal stays paid)
            when = at(day, 12, 41) if outcome else self._between(at(day, 12, 5), at(day, 14, 25))
            if outcome or self.rng.random() < 0.85:
                self._on(when, lambda r=reservation: reservations.scan(r.qr_signed_payload, by=scanner))
            else:
                self._on(when, lambda r=reservation: reservations.manual_checkin(r, by=scanner))

    def _run(self):
        done = 0
        while self.events:
            self.events.sort(key=lambda e: (e[0], e[1]))
            when, _, fn = self.events.pop(0)
            with clock.frozen(when):
                fn()
                failed = [name for name, result in tick().items() if result == -1]
            if failed:
                raise CommandError(f"Scheduler jobs failed at {when:%Y-%m-%d %H:%M}: {failed}")
            done += 1
        self.stdout.write(f"  {done} steps replayed.")

    def _summary(self):
        self.stdout.write("\nTest week:")
        for menu in Menu.objects.filter(date__range=(self.days[0], self.days[-1])).order_by("date"):
            rows = Reservation.objects.filter(menu=menu)
            counts = {s: rows.filter(status=s).count() for s in Reservation.Status.values}
            split = "/".join(str(rows.exclude(status="cancelled").filter(choice=c).count()) for c in menu.choices())
            self.stdout.write(f"  {menu.date:%a %d/%m}  {menu.status:<9} menus={len(menu.choices())} ({split}) "
                              f"reserved={counts['reserved']} served={counts['served']} no_show={counts['no_show']} "
                              f"cancelled={counts['cancelled']}  price={menu.price if menu.is_paid else 'free'}")
        persona = User.objects.get(work_email=PERSONA)
        self.stdout.write(f"\n{PERSONA}: balance {persona.balance} TND")

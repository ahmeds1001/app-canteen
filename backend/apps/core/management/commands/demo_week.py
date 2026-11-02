"""Development only: add a realistic test week (Mon 9 – Sat 14 Nov 2026) to the current database.

    python manage.py demo_week

Nothing is deleted or overwritten: existing accounts and dishes are reused, missing ones are added, and the
week is built only if none of its days has a menu yet (running it twice does nothing the second time).

Every step goes through the real services under a frozen clock, and the scheduler runs at each step, so locks,
finalizations, scans, no-shows, notifications and the audit log are what the app itself would have produced.
At the end the test clock is set to Tuesday 10 Nov 20:30. The test scenarios: docs/guide-test-semaine.md.
"""
import os
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services as accounts
from apps.accounts.models import User
from apps.core import clock
from apps.core.management.commands.run_scheduler import tick
from apps.core.models import CanteenSettings
from apps.menus import services as menus
from apps.menus.models import Dish, Menu
from apps.notifications import events as notification_events
from apps.reservations import services as reservations
from apps.reservations.models import Reservation

TZ = ZoneInfo(settings.TIME_ZONE)
MON, TUE, WED, THU, FRI, SAT = (date(2026, 11, 9) + timedelta(days=n) for n in range(6))
START = datetime(2026, 11, 10, 20, 30, tzinfo=TZ)  # Tuesday evening: Wednesday can still be reserved
PERSONA = "employee@ovagri.test"  # the account the guide uses to test as an employee

STAFF = {  # email: (first name, last name, role, matricule)
    "admin@ovagri.test": ("Admin", "Test", User.Role.ADMIN, "ADM-001"),
    PERSONA: ("Employe", "Test", User.Role.EMPLOYEE, "EMP-001"),
    "hr@ovagri.test": ("RH", "Test", User.Role.HR, "RH-001"),
    "chef@ovagri.test": ("Chef", "Test", User.Role.CHEF, "CHEF-001"),
    "scanner@ovagri.test": ("Scanner", "Test", User.Role.SCANNER, "SCAN-001"),
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
    "Fruit de saison": ("dessert", "", ""),
    "Yaourt nature": ("dessert", "lait", ""),
    "Crème au chocolat": ("dessert", "lait", ""),
    "Makroud": ("dessert", "gluten", "Gâteau de semoule aux dattes"),
}
MENUS = {
    MON: ["Chorba frik", "Couscous au poulet", "Fruit de saison"],
    TUE: ["Salade mechouia", "Riz djerbien", "Yaourt nature"],
    WED: ["Brik à l'œuf", "Pâtes au thon", "Crème au chocolat"],
    THU: ["Salade tunisienne", "Mloukhia au bœuf", "Fruit de saison"],
    FRI: ["Chorba frik", "Couscous au poisson", "Makroud"],
    SAT: ["Salade mechouia", "Escalope panée et frites", "Yaourt nature"],  # left as a draft for the chef
}
SHARE_RESERVING = {MON: 0.8, TUE: 0.75, WED: 0.7, THU: 0.55, FRI: 0.35}
PERSONA_DAYS = {MON: "no_show", TUE: "served", THU: "reserved"}  # Wed and Fri: the persona reserves in the test


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=TZ)


class Command(BaseCommand):
    help = "Add a test week (9–14 Nov 2026) to the current database and set the test clock (DEBUG only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("demo_week is only available when DEBUG is on.")
        password = os.environ.get("DEV_SEED_PASSWORD")
        if not password:
            raise CommandError("Set DEV_SEED_PASSWORD in .env: it becomes the password of the accounts created.")
        self.rng = random.Random(1109)
        self.events: list[tuple[datetime, int, object]] = []

        users = self._users(password)
        dishes = self._dishes(users["chef"])
        if Menu.objects.filter(date__range=(MON, SAT)).exists():
            self.stdout.write("The week of 9 Nov already has menus: nothing more to build.")
        else:
            self._plan_week(users, dishes)
            self._run()
        call_command("dev_clock", "set", START.strftime("%Y-%m-%d"), START.strftime("%H:%M"), stdout=self.stdout)
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
        self.pending = [
            self._user(f"{first.lower()}.{last.lower()}@ovagri.test", first, last, password, department=dept,
                       status=User.Status.PENDING_HR)
            for first, last, dept in PENDING
        ]
        return found

    def _dishes(self, chef) -> dict:
        dishes = {}
        for name, (category, allergens, description) in DISHES.items():
            dish = Dish.objects.filter(name=name, is_archived=False).first()
            if dish is None:
                with clock.frozen(at(date(2026, 11, 4), 15)):
                    dish = menus.create_dish(by=chef, name=name, category=category, allergens=allergens,
                                             description=description)
            dishes[name] = dish
        return dishes

    # --- The week, as a list of timed events ------------------------------------------------
    def _on(self, when: datetime, fn):
        self.events.append((when, len(self.events), fn))

    def _plan_week(self, users, dishes):
        chef, hr, management, scanner, persona = (users[k] for k in ("chef", "hr", "management", "scanner", "persona"))
        cfg = CanteenSettings.load()
        if not cfg.payment_enabled:
            cfg.payment_enabled = True  # so Friday can be a paid day (cash at the counter, FR-32 to FR-36)
            cfg.save()

        # The scheduler runs at the key moments of every day, which also settles the older test days.
        day = date(2026, 11, 5)
        while at(day, 0, 1) < START:
            for hh, mm in ((0, 1), (8, 0), (10, 0), (15, 1), (20, 0)):
                if at(day, hh, mm) < START:
                    self._on(at(day, hh, mm), lambda: None)
            day += timedelta(days=1)

        # Chef: Mon–Wed published Thursday 5, Thu–Fri on Friday 6, Saturday still a draft on Tuesday.
        menu_ids = {}

        def build(day, publish=True):
            def run():
                menu = menus.get_or_create_menu(day, by=chef)
                menus.set_items(menu, [dishes[n].pk for n in MENUS[day]], by=chef)
                if publish:
                    menus.publish(menu, by=chef)
                menu_ids[day] = menu.pk
            return run

        for day in (MON, TUE, WED):
            self._on(at(date(2026, 11, 5), 9), build(day))
        for day in (THU, FRI):
            self._on(at(date(2026, 11, 6), 9), build(day))
        self._on(at(TUE, 10), build(SAT, publish=False))

        # Management makes Friday a paid day before anyone reserves it.
        self._on(at(MON, 10), lambda: menus.set_payment(Menu.objects.get(pk=menu_ids[FRI]), is_paid=True,
                                                         price=Decimal("3.500"), by=management))

        # HR suspends one employee; two new sign-ups wait for HR on Tuesday evening.
        self._on(at(MON, 11), lambda: accounts.change_status(self.suspended, "suspend", by=hr))
        for i, user in enumerate(self.pending):
            self._on(at(TUE, 18, 10 + 40 * i), lambda user=user: notification_events.account_pending(user))

        # Reservations (and a few cancellations) between D-3 and the evening before, never after START.
        for day, share in SHARE_RESERVING.items():
            opens = max(at(day - timedelta(days=3), 8), at(date(2026, 11, 6), 10))
            closes = min(at(day - timedelta(days=1), 22, 30), START - timedelta(minutes=10))
            for user in self.employees:
                if self.rng.random() < share:
                    self._reserve(user, day, self._between(opens, closes), closes)
            if PERSONA_DAYS.get(day):
                self._reserve(persona, day, self._between(opens, closes), closes, may_cancel=False)

        # Service days already past: Monday auto-finalized at 10:00, Tuesday confirmed by management at 09:20.
        self._on(at(TUE, 9, 20), lambda: self._finalize(menu_ids[TUE], management, extra=2))
        for day in (MON, TUE):
            self._on(at(day, 11, 59), lambda day=day: self._plan_service(day, scanner, persona))

    def _between(self, start: datetime, end: datetime) -> datetime:
        minutes = int((end - start).total_seconds() // 60)
        return start + timedelta(minutes=self.rng.randint(0, max(minutes, 0)))

    def _reserve(self, user, day, when, closes, may_cancel=True):
        def run():
            menu = Menu.objects.get(date=day)
            reservation = reservations.reserve(user, menu)
            if may_cancel and self.rng.random() < 0.08:
                self._on(self._between(when + timedelta(minutes=5), closes),
                         lambda: reservations.cancel(reservation, by=user))
        self._on(when, run)

    def _finalize(self, menu_pk, management, extra):
        menu = Menu.objects.get(pk=menu_pk)
        menus.finalize(menu, final_plate_count=menus.proposed_plate_count(menu)["proposed"] + extra, by=management)

    def _plan_service(self, day, scanner, persona):
        """Called at 11:59: schedule the check-ins of the day's reservations between 12:05 and 14:25."""
        for reservation in Reservation.objects.filter(date=day, status=Reservation.Status.RESERVED):
            outcome = PERSONA_DAYS.get(day) if reservation.user_id == persona.pk else None
            if outcome == "no_show" or (outcome is None and self.rng.random() > 0.88):
                continue  # becomes a no-show at 15:00
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
        for menu in Menu.objects.filter(date__range=(MON, SAT)).order_by("date"):
            rows = Reservation.objects.filter(menu=menu)
            counts = {s: rows.filter(status=s).count() for s in Reservation.Status.values}
            self.stdout.write(f"  {menu.date:%a %d/%m}  {menu.status:<9} reserved={counts['reserved']} "
                              f"served={counts['served']} no_show={counts['no_show']} cancelled={counts['cancelled']}"
                              f"{'  paid ' + str(menu.price) if menu.is_paid else ''}")

"""FR-41: the admin gives roles from the app's Comptes screen."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import User
from apps.core.exceptions import DomainError
from apps.core.models import AuditLog
from apps.core.tests import factories as f


class RoleTests(TestCase):
    def setUp(self):
        self.admin = f.user(role="admin")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _set(self, user, role, client=None):
        return (client or self.client).post(f"/api/v1/auth/users/{user.pk}/role/", {"role": role}, format="json")

    def test_admin_changes_a_role_and_it_is_audited(self):
        user = f.user()
        response = self._set(user, "chef")
        self.assertEqual((response.status_code, response.json()["role"]), (200, "chef"))
        log = AuditLog.objects.get(action=AuditLog.Action.ROLE_CHANGE, target_id=str(user.pk))
        self.assertEqual((log.actor, log.old_value, log.new_value, log.meta["source"]),
                         (self.admin, "employee", "chef", "app"))

    def test_admin_role_opens_and_closes_the_admin_site(self):
        user = f.user()
        self._set(user, "admin")
        user.refresh_from_db()
        self.assertTrue(user.is_staff and user.is_superuser)
        self._set(user, "employee")
        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_hr_cannot_change_roles(self):
        hr = APIClient()
        hr.force_authenticate(f.user(role="hr"))
        user = f.user()
        response = self._set(user, "chef", client=hr)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "admin_only"))
        user.refresh_from_db()
        self.assertEqual(user.role, "employee")

    def test_no_change_to_own_role(self):
        self.assertEqual(self._set(self.admin, "employee").json()["code"], "cannot_change_own_role")

    def test_another_admin_can_be_demoted_while_one_remains(self):
        second = f.user(role="admin")
        self.assertEqual(self._set(second, "employee").status_code, 200)

    def test_last_active_admin_keeps_the_role(self):
        # Only `last` is an active admin; another admin account exists but is suspended.
        last = f.user(role="admin")
        self.admin.status = User.Status.SUSPENDED
        self.admin.save()
        with self.assertRaises(DomainError) as ctx:
            services.change_role(last, "employee", by=self.admin)
        self.assertEqual(ctx.exception.code, "last_admin")
        last.refresh_from_db()
        self.assertEqual(last.role, "admin")

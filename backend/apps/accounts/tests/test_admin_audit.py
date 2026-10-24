"""Role and status changes made in the Django admin are audited (spec §5 Security)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.tests import factories as f

A = AuditLog.Action


class AdminAuditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "it@example.com", "Str0ng-pass-123", first_name="IT", last_name="Admin"
        )
        self.client.force_login(self.admin)

    def _post(self, user: User, **changes):
        data = {
            "work_email": user.work_email, "first_name": user.first_name, "last_name": user.last_name,
            "employee_number": user.employee_number, "department": user.department,
            "preferred_language": user.preferred_language, "role": user.role, "status": user.status,
            "rejection_reason": user.rejection_reason,
            **changes,
        }
        data = {k: v for k, v in data.items() if v is not False}  # unchecked boxes are not sent
        response = self.client.post(reverse("admin:accounts_user_change", args=[user.pk]), data)
        self.assertEqual(response.status_code, 302)  # 200 = the form was rejected

    def _logs(self, user: User):
        return AuditLog.objects.filter(target_type="accounts.user", target_id=str(user.pk))

    def test_role_change_is_audited(self):
        user = f.user()
        self._post(user, role="chef")
        log = self._logs(user).get(action=A.ROLE_CHANGE)
        self.assertEqual((log.actor, log.old_value, log.new_value), (self.admin, "employee", "chef"))
        self.assertEqual(log.meta["source"], "django_admin")

    def test_admin_rights_change_is_audited(self):
        user = f.user()
        self._post(user, is_staff="on")
        log = self._logs(user).get(action=A.ROLE_CHANGE)
        self.assertEqual(log.meta["is_staff"], "False -> True")

    def test_status_changes_use_the_matching_action(self):
        user = f.user(status=User.Status.PENDING_HR)
        self._post(user, status="active")
        user.refresh_from_db()
        self._post(user, status="suspended")
        user.refresh_from_db()
        self._post(user, status="pending_hr")
        actions = list(self._logs(user).order_by("id").values_list("action", flat=True))
        self.assertEqual(actions, [A.APPROVE, A.SUSPEND, A.STATUS_CHANGE])

    def test_saving_without_access_change_writes_nothing(self):
        user = f.user()
        self._post(user, department="Logistique")
        self.assertFalse(self._logs(user).exists())

    def test_users_cannot_be_deleted_from_the_admin(self):
        user = f.user()
        response = self.client.get(reverse("admin:accounts_user_delete", args=[user.pk]))
        self.assertEqual(response.status_code, 403)

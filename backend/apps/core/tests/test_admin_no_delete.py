from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.core.tests import factories as f


class AdminNoDeleteTests(TestCase):
    """Rule 4: data is never deleted, not even by a superuser in the Django admin."""

    def setUp(self):
        self.admin_user = f.user(role="admin", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin_user)

    def test_no_app_model_can_be_deleted_from_the_admin(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        checked = []
        for model, model_admin in admin.site._registry.items():
            if not model.__module__.startswith("apps."):
                continue
            self.assertFalse(model_admin.has_delete_permission(request), model.__name__)
            for inline in model_admin.get_inline_instances(request):
                self.assertFalse(inline.has_delete_permission(request), inline.model.__name__)
            checked.append(model.__name__)
        for name in ("Reservation", "Menu", "Dish", "EmployeeRoster", "BalanceTransaction", "User"):
            self.assertIn(name, checked)

    def test_delete_page_is_refused(self):
        chef = f.user(role="chef")
        dish = f.dish(chef)
        with self.assertLogs("django.request", "WARNING"):  # Django logs the 403
            r = self.client.post(f"/admin/menus/dish/{dish.pk}/delete/", {"post": "yes"})
        self.assertEqual(r.status_code, 403)
        dish.refresh_from_db()  # still there

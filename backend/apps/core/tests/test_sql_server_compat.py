from django.apps import apps
from django.db.models import Q, UniqueConstraint
from django.test import SimpleTestCase


def _negated(q: Q) -> bool:
    return q.negated or any(isinstance(child, Q) and _negated(child) for child in q.children)


class SqlServerCompatTests(SimpleTestCase):
    """Production runs on SQL Server: a filtered unique index there refuses NOT (...) in its WHERE clause."""

    def test_no_negated_condition_in_unique_constraints(self):
        for model in apps.get_models():
            for constraint in model._meta.constraints:
                if isinstance(constraint, UniqueConstraint) and constraint.condition is not None:
                    self.assertFalse(_negated(constraint.condition), f"{model.__name__}.{constraint.name}")

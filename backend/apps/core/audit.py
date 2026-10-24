"""Single entry point for writing to the audit log."""
from typing import Any

from django.db import models

from .models import AuditLog


def record(
    action: str,
    *,
    actor=None,
    target: models.Model | None = None,
    old_value: Any = "",
    new_value: Any = "",
    **meta: Any,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        target_type=target._meta.label_lower if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        old_value=str(old_value),
        new_value=str(new_value),
        meta={k: str(v) for k, v in meta.items()},
    )

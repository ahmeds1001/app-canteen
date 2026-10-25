"""Web Push sender (VAPID). Keys come from .env; without them push is off and notifications stay in-app."""
import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def send(subscription, payload: dict) -> bool:
    """Send one push. Returns False when the browser has dropped the subscription (404/410)."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},  # fresh dict: pywebpush adds aud/exp to it
            ttl=24 * 3600,
            timeout=10,
        )
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return False
        logger.warning("Push to subscription %s failed (%s): %s", subscription.pk, status, exc)
        return True
    except Exception:  # network error: keep the subscription, the in-app notification is there anyway
        logger.exception("Push to subscription %s failed", subscription.pk)
        return True

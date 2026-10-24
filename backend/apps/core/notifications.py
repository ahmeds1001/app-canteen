"""Outgoing emails (spec §8). Templates live in templates/emails/<name>.txt.

Kept deliberately simple: one function per message, plain-text bodies.
Swap `send` for a queue later if email volume ever requires it.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send(template: str, to: list[str], subject: str, context: dict) -> None:
    body = render_to_string(f"emails/{template}.txt", context)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to, fail_silently=False)
    except Exception:  # never break the request because SMTP is down; log it
        logger.exception("Email %s to %s failed", template, to)


def otp_code(user, code: str) -> None:
    # The code is in the subject so it can be read from the phone notification.
    send("otp_code", [user.work_email], f"{code} - Code de vérification Cantine", {"user": user, "code": code})


def account_approved(user) -> None:
    send("account_approved", [user.work_email], "Votre compte Cantine est actif",
         {"user": user, "login_url": settings.FRONTEND_URL + "/login"})


def account_rejected(user) -> None:
    send("account_rejected", [user.work_email], "Votre demande de compte Cantine", {"user": user})


def password_reset_link(user, token: str) -> None:
    url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send("password_reset", [user.work_email], "Réinitialisation du mot de passe Cantine", {"user": user, "url": url})


def password_changed(user) -> None:
    send("password_changed", [user.work_email], "Votre mot de passe Cantine a été modifié", {"user": user})

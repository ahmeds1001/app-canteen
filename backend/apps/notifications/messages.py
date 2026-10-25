"""Notification texts (spec §8), French and English. One place for both the in-app list and the phone push.

Params are stored on the Notification; dates are ISO strings ("2026-10-29") and are formatted here per language.
"""
from datetime import date

from .models import Notification

K = Notification.Kind

_DAYS = {
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
_MONTHS = {
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}

# kind -> language -> (title, body). Bodies use str.format with the prepared params.
TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    K.ACCOUNTS_PENDING: {
        "fr": ("Nouveau compte à valider", "{name} ({number}) attend votre validation — {roster}."),
        "en": ("New account to approve", "{name} ({number}) is waiting for approval — {roster}."),
    },
    K.MENU_CHANGED: {
        "fr": ("Menu modifié",
               "Le menu du {date} a changé : {dishes}. Vous pouvez annuler avant minuit la veille."),
        "en": ("Menu changed",
               "The menu for {date} has changed: {dishes}. You can cancel until midnight the day before."),
    },
    K.MENU_ANNOUNCED: {
        "fr": ("Menu annoncé", "Le menu du {date} est connu : {dishes}."),
        "en": ("Menu announced", "The menu for {date} is out: {dishes}."),
    },
    K.PRICE_CHANGED: {
        "fr": ("Prix du repas modifié",
               "Le repas du {date} est maintenant {price}. Vous pouvez annuler avant minuit la veille."),
        "en": ("Meal price changed",
               "The meal on {date} is now {price}. You can cancel until midnight the day before."),
    },
    K.DAY_CLOSED: {
        "fr": ("Cantine fermée", "La cantine est fermée le {date}{reason}. Votre réservation est annulée."),
        "en": ("Canteen closed", "The canteen is closed on {date}{reason}. Your reservation is cancelled."),
    },
    K.PLACEHOLDER_PUBLISHED: {
        "fr": ("Menu à compléter",
               "Le {date} est ouvert en « Menu à venir ». Ajoutez les plats avant la clôture."),
        "en": ("Menu to complete",
               "{date} is open as \"Menu to be announced\". Add the dishes before the cutoff."),
    },
    K.PLACEHOLDER_EMPTY_AT_CUTOFF: {
        "fr": ("Menu toujours vide",
               "Le {date} a {reserved} réservation(s) mais aucun plat. "
               "Le chef peut encore les ajouter avant le service."),
        "en": ("Menu still empty",
               "{date} has {reserved} reservation(s) but no dishes. The chef can still add them before service."),
    },
    K.FINALIZATION_REMINDER: {
        "fr": ("Assiettes à confirmer",
               "{reserved} réservation(s) pour aujourd'hui ({date}). "
               "Confirmez le nombre d'assiettes avant {time}."),
        "en": ("Confirm the plate count",
               "{reserved} reservation(s) today ({date}). Confirm the number of plates before {time}."),
    },
    K.DAY_FINALIZED: {
        "fr": ("Nombre d'assiettes",
               "{date} : {plates} assiettes à préparer ({reserved} réservations + {buffer} de marge)."),
        "en": ("Plate count",
               "{date}: {plates} plates to prepare ({reserved} reservations + {buffer} extra)."),
    },
    K.MENU_MISSING: {
        "fr": ("Menus à publier", "Pas encore de menu publié pour : {dates}."),
        "en": ("Menus to publish", "No menu published yet for: {dates}."),
    },
    K.RESERVATION_REMINDER: {
        "fr": ("Réservez pour demain",
               "Vous n'avez pas réservé pour demain ({date}) : {dishes}. Réservez avant minuit."),
        "en": ("Reserve for tomorrow",
               "You have not reserved for tomorrow ({date}): {dishes}. Reserve before midnight."),
    },
}

_WORDS = {
    "fr": {"on_roster": "sur la liste", "not_on_roster": "hors liste", "free": "gratuit",
           "paid": "payant ({price} TND)", "tba": "menu à venir"},
    "en": {"on_roster": "on the list", "not_on_roster": "not on the list", "free": "free",
           "paid": "paid ({price} TND)", "tba": "menu to be announced"},
}


def language(code: str | None) -> str:
    return "en" if (code or "").lower().startswith("en") else "fr"


def format_day(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso)
    text = f"{_DAYS[lang][d.weekday()]} {d.day} {_MONTHS[lang][d.month - 1]}"
    return text if lang == "fr" else f"{text.split(' ', 1)[0]}, {_MONTHS[lang][d.month - 1]} {d.day}"


def render(kind: str, params: dict, lang: str) -> tuple[str, str]:
    lang = language(lang)
    words = _WORDS[lang]
    p = dict(params)
    if "date" in p:
        p["date"] = format_day(p["date"], lang)
    if "dates" in p:
        p["dates"] = ", ".join(format_day(d, lang) for d in p["dates"])
    if "dishes" in p:
        p["dishes"] = " · ".join(p["dishes"]) or words["tba"]
    if "on_roster" in p:
        p["roster"] = words["on_roster" if p["on_roster"] else "not_on_roster"]
    if "is_paid" in p:
        p["price"] = words["paid"].format(price=p.get("price")) if p["is_paid"] else words["free"]
    if "reason" in p:
        p["reason"] = f" ({p['reason']})" if p["reason"] else ""
    title, body = TEXTS[kind][lang]
    return title, body.format(**p)

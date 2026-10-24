"""Dish library, daily menus and menu items (spec §3.2, §3.4, §6.1)."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class DishCategory(models.TextChoices):
    STARTER = "starter", "Starter"
    MAIN = "main", "Main"
    DESSERT = "dessert", "Dessert"
    SIDE = "side", "Side"
    DRINK = "drink", "Drink"


class Dish(TimeStampedModel):
    """The chef's reusable library (FR-29 to FR-31)."""

    name = models.CharField(max_length=120, db_index=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=10, choices=DishCategory.choices, default=DishCategory.MAIN)
    allergens = models.CharField(max_length=255, blank=True, help_text="Comma-separated list.")
    photo = models.ImageField(upload_to="dishes/", blank=True)
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["category", "name"]
        verbose_name_plural = "dishes"

    def __str__(self) -> str:
        return self.name


class Menu(TimeStampedModel):
    """One menu per date. Lifecycle: Draft → Published → Locked → Finalized → Closed (§6.3)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        LOCKED = "locked", "Locked"
        FINALIZED = "finalized", "Finalized"
        CLOSED = "closed", "Closed"

    date = models.DateField(unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_placeholder = models.BooleanField(default=False, help_text="Auto-published at the D-2 deadline (FR-38).")
    menu_announced_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=120, blank=True)

    # Finalization (FR-24 to FR-27)
    final_plate_count = models.PositiveIntegerField(null=True, blank=True)
    buffer = models.PositiveIntegerField(null=True, blank=True)
    reserved_count_at_finalization = models.PositiveIntegerField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    auto_finalized = models.BooleanField(default=False)

    # Payment (FR-32), frozen at cutoff
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )  # NULL = created by the scheduler (placeholder)

    class Meta:
        ordering = ["date"]

    def __str__(self) -> str:
        return f"Menu {self.date} ({self.status})"

    @property
    def is_reservable_status(self) -> bool:
        return self.status == self.Status.PUBLISHED


class MenuItem(models.Model):
    """A dish on a given menu. Dish details are SNAPSHOTTED (business rule "Dish snapshot")."""

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    dish = models.ForeignKey(Dish, null=True, on_delete=models.SET_NULL, related_name="menu_items")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=10, choices=DishCategory.choices)
    allergens = models.CharField(max_length=255, blank=True)
    photo = models.CharField(max_length=255, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.name

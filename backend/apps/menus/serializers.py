from django.core.files.storage import default_storage
from rest_framework import serializers

from . import rules
from .models import Dish, Menu, MenuItem


class RelativeImageField(serializers.ImageField):
    """Always `/media/…`: an absolute URL would name the backend's own host (localhost:8000 behind the dev
    proxy, an internal host behind the production proxy), which a phone cannot reach."""

    def to_representation(self, value):
        return value.url if value else None


class DishSerializer(serializers.ModelSerializer):
    last_served_on = serializers.DateField(read_only=True, allow_null=True)
    photo = RelativeImageField(required=False, allow_null=True)

    class Meta:
        model = Dish
        fields = ["id", "name", "description", "category", "allergens", "photo", "is_archived", "last_served_on"]
        read_only_fields = ["is_archived"]


class MenuItemSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = ["id", "dish", "name", "description", "category", "allergens", "photo", "photo_url", "position"]

    def get_photo_url(self, obj: MenuItem) -> str | None:
        # `photo` is the snapshot of the dish's stored file name (FR-30); the URL is built like ImageField's.
        return default_storage.url(obj.photo) if obj.photo else None


class MenuSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    reservation_cutoff = serializers.SerializerMethodField()
    is_open_for_reservation = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = [
            "id", "date", "status", "is_placeholder", "menu_announced_at", "published_at", "items",
            "is_paid", "price", "reservation_cutoff", "is_open_for_reservation",
        ]

    def get_reservation_cutoff(self, obj: Menu) -> str:
        return rules.reservation_cutoff(obj.date).isoformat()

    def get_is_open_for_reservation(self, obj: Menu) -> bool:
        from apps.core import clock

        return obj.status == Menu.Status.PUBLISHED and clock.now() <= rules.reservation_cutoff(obj.date)


class MenuStaffSerializer(MenuSerializer):
    """Extra fields for chef / management."""

    reserved_count = serializers.IntegerField(read_only=True)

    class Meta(MenuSerializer.Meta):
        fields = MenuSerializer.Meta.fields + [
            "reserved_count", "final_plate_count", "buffer", "auto_finalized", "finalized_at", "closed_reason",
        ]


class MenuCreateSerializer(serializers.Serializer):
    date = serializers.DateField()


class SetItemsSerializer(serializers.Serializer):
    dish_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class CloseDaySerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class FinalizeSerializer(serializers.Serializer):
    final_plate_count = serializers.IntegerField(min_value=0)


class PaymentSerializer(serializers.Serializer):
    is_paid = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=8, decimal_places=3, required=False, allow_null=True)

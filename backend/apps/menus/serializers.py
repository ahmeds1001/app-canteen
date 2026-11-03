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
        fields = ["id", "choice", "dish", "name", "description", "category", "allergens", "photo", "photo_url",
                  "position"]

    def get_photo_url(self, obj: MenuItem) -> str | None:
        # `photo` is the snapshot of the dish's stored file name (FR-30); the URL is built like ImageField's.
        return default_storage.url(obj.photo) if obj.photo else None


class MenuSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    choices = serializers.SerializerMethodField()
    reservation_cutoff = serializers.SerializerMethodField()
    is_open_for_reservation = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = [
            "id", "date", "status", "is_placeholder", "menu_announced_at", "published_at", "items", "choices",
            "is_paid", "price", "reservation_cutoff", "is_open_for_reservation",
        ]

    def get_choices(self, obj: Menu) -> list[int]:
        return obj.choices()

    def get_reservation_cutoff(self, obj: Menu) -> str:
        return rules.reservation_cutoff(obj.date).isoformat()

    def get_is_open_for_reservation(self, obj: Menu) -> bool:
        from apps.core import clock

        return obj.status == Menu.Status.PUBLISHED and clock.now() <= rules.reservation_cutoff(obj.date)


class MenuStaffSerializer(MenuSerializer):
    """Extra fields for chef / management."""

    reserved_count = serializers.IntegerField(read_only=True)
    reserved_by_choice = serializers.SerializerMethodField()

    class Meta(MenuSerializer.Meta):
        fields = MenuSerializer.Meta.fields + [
            "reserved_count", "reserved_by_choice", "final_plate_count", "final_plates_by_choice", "buffer",
            "auto_finalized", "finalized_at", "closed_reason",
        ]

    def get_reserved_by_choice(self, obj: Menu) -> dict[str, int]:
        from .services import reserved_by_choice

        return {str(choice): n for choice, n in reserved_by_choice(obj).items()}


class MenuCreateSerializer(serializers.Serializer):
    date = serializers.DateField()


class SetItemsSerializer(serializers.Serializer):
    dish_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)  # menu 1
    dish_ids_2 = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)  # menu 2


class CloseDaySerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class FinalizeSerializer(serializers.Serializer):
    """Plates per menu: {"plates": {"1": 25, "2": 12}}."""

    plates = serializers.DictField(child=serializers.IntegerField(min_value=0), allow_empty=False)

    def validate_plates(self, value):
        if not set(value) <= {"1", "2"}:
            raise serializers.ValidationError("Menus are numbered 1 and 2.")
        return {int(k): v for k, v in value.items()}


class PaymentSerializer(serializers.Serializer):
    is_paid = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=8, decimal_places=3, required=False, allow_null=True)

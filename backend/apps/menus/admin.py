from django.contrib import admin

from .models import Dish, Menu, MenuItem


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_archived")
    list_filter = ("category", "is_archived")
    search_fields = ("name",)


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("date", "status", "is_placeholder", "final_plate_count", "is_paid")
    list_filter = ("status", "is_placeholder")
    inlines = [MenuItemInline]

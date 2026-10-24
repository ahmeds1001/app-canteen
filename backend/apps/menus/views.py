from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.permissions import IsChef, IsChefOrManagement, IsEmployee, IsManagement

from . import selectors, services
from .models import Menu
from .serializers import (
    CloseDaySerializer,
    DishSerializer,
    FinalizeSerializer,
    MenuCreateSerializer,
    MenuSerializer,
    MenuStaffSerializer,
    PaymentSerializer,
    SetItemsSerializer,
)

STAFF_ROLES = {"chef", "management", "admin"}


class DishViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsChef]
    serializer_class = DishSerializer

    def get_queryset(self):
        p = self.request.query_params
        return selectors.dishes(
            q=p.get("q", ""), category=p.get("category", ""), include_archived=p.get("archived") == "1"
        )

    def create(self, request):
        data = DishSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        dish = services.create_dish(by=request.user, **data.validated_data)
        return Response(DishSerializer(dish).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        dish = self.get_object()
        data = DishSerializer(dish, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(DishSerializer(services.update_dish(dish, by=request.user, **data.validated_data)).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return Response(DishSerializer(services.archive_dish(self.get_object(), by=request.user)).data)


class MenuViewSet(GenericViewSet):
    lookup_field = "date"
    lookup_value_regex = r"\d{4}-\d{2}-\d{2}"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsEmployee()]
        if self.action in ("finalization", "finalize", "payment"):
            return [IsManagement()]
        if self.action == "close":
            return [IsChefOrManagement()]
        return [IsChef()]

    def _is_staff(self) -> bool:
        return self.request.user.role in STAFF_ROLES

    def _serialize(self, menu: Menu):
        if self._is_staff():
            menu.reserved_count = services.reserved_count(menu)
            return MenuStaffSerializer(menu).data
        return MenuSerializer(menu).data

    def _menu(self, date) -> Menu:
        return get_object_or_404(Menu, date=parse_date(date))

    def list(self, request):
        p = request.query_params
        qs = selectors.menus(start=parse_date(p.get("from", "") or "") if p.get("from") else None,
                             end=parse_date(p.get("to", "") or "") if p.get("to") else None,
                             staff=self._is_staff())
        serializer = MenuStaffSerializer if self._is_staff() else MenuSerializer
        return Response(serializer(qs, many=True).data)

    def retrieve(self, request, date=None):
        menu = self._menu(date)
        if not self._is_staff() and menu.status not in selectors.VISIBLE_TO_EMPLOYEES:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(self._serialize(menu))

    def create(self, request):
        data = MenuCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        menu = services.get_or_create_menu(data.validated_data["date"], by=request.user)
        return Response(self._serialize(menu), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put"])
    def items(self, request, date=None):
        data = SetItemsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        menu = services.set_items(self._menu(date), data.validated_data["dish_ids"], by=request.user)
        return Response(self._serialize(menu))

    @action(detail=True, methods=["post"])
    def publish(self, request, date=None):
        return Response(self._serialize(services.publish(self._menu(date), by=request.user)))

    @action(detail=True, methods=["post"])
    def close(self, request, date=None):
        data = CloseDaySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        menu = services.close_day(self._menu(date), by=request.user, reason=data.validated_data["reason"])
        return Response(self._serialize(menu))

    @action(detail=True, methods=["get"])
    def finalization(self, request, date=None):
        return Response(services.proposed_plate_count(self._menu(date)))

    @action(detail=True, methods=["post"])
    def finalize(self, request, date=None):
        data = FinalizeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        menu = services.finalize(
            self._menu(date), final_plate_count=data.validated_data["final_plate_count"], by=request.user
        )
        return Response(self._serialize(menu))

    @action(detail=True, methods=["post"])
    def payment(self, request, date=None):
        data = PaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        menu = services.set_payment(self._menu(date), by=request.user, **data.validated_data)
        return Response(self._serialize(menu))

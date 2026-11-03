import csv

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.core import audit, clock
from apps.core.permissions import IsEmployee, IsScanner, IsScannerOrManagement
from apps.menus.models import Menu

from . import selectors, services
from .models import Reservation
from .serializers import (
    DayReservationSerializer,
    ReservationSerializer,
    ReserveSerializer,
    ScanResultSerializer,
    ScanSerializer,
)


class MyReservationViewSet(GenericViewSet):
    """The logged-in employee's own reservations."""

    permission_classes = [IsEmployee]
    serializer_class = ReservationSerializer

    def get_queryset(self):
        qs = Reservation.objects.filter(user=self.request.user).select_related("menu").prefetch_related("menu__items")
        if self.request.query_params.get("upcoming") == "1":
            qs = qs.filter(date__gte=clock.today()).order_by("date")
        return qs

    def list(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def create(self, request):
        data = ReserveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        menu = get_object_or_404(Menu, date=data.validated_data["date"])
        reservation = services.reserve(request.user, menu, choice=data.validated_data["choice"])
        return Response(self.get_serializer(reservation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reservation = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(self.get_serializer(services.cancel(reservation, by=request.user)).data)


class DayListView(APIView):
    """A day's reservation list, any day (scanner and management). `?format=csv` downloads it."""

    permission_classes = [IsScannerOrManagement]

    def get(self, request):
        p = request.query_params
        day = parse_date(p.get("date", "")) or clock.today()
        rows = selectors.day_list(day, status=p.get("status", ""), q=p.get("q", "").strip())
        if p.get("export") == "csv":
            audit.record(audit.AuditLog.Action.DATA_EXPORT, actor=request.user, report="day_list",
                         date=day.isoformat(), rows=rows.count())
            return _csv(day, DayReservationSerializer(rows, many=True).data)
        return Response({**selectors.day_summary(day), "rows": DayReservationSerializer(rows, many=True).data})


def _csv(day, rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reservations-{day.isoformat()}.csv"'
    response.write("﻿")  # BOM: Excel opens the accents correctly
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["nom", "matricule", "departement", "menu", "statut", "paiement", "montant", "reserve_le",
                     "servi_le", "methode"])
    for r in rows:
        writer.writerow([r["full_name"], r["employee_number"] or "", r["department"], r["choice"], r["status"],
                         r["payment_status"], r["amount_due"] or "", r["reserved_at"], r["served_at"] or "",
                         r["scan_method"]])
    return response


class ScanView(APIView):
    """Canteen phone: validate a QR code (FR-18, FR-19)."""

    permission_classes = [IsScanner]

    def post(self, request):
        data = ScanSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        reservation = services.scan(
            data.validated_data["payload"], by=request.user, scanned_at=data.validated_data.get("scanned_at")
        )
        return Response(ScanResultSerializer(reservation).data)


class CheckinViewSet(GenericViewSet):
    """Manual fallback (FR-20) for the canteen phone. Meals are paid from the balance, never at the counter."""

    permission_classes = [IsScanner]
    serializer_class = ScanResultSerializer

    def get_queryset(self):
        return Reservation.objects.active().select_related("user", "menu").prefetch_related("menu__items")

    def list(self, request):
        """Search today's reservations by name or employee number: ?q=..."""
        day = parse_date(request.query_params.get("date", "")) or clock.today()
        qs = self.get_queryset().filter(date=day)
        if q := request.query_params.get("q", "").strip():
            qs = qs.filter(
                Q(user__last_name__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__employee_number__icontains=q)
            )
        return Response(self.get_serializer(qs[:30], many=True).data)

    @action(detail=True, methods=["post"])
    def manual(self, request, pk=None):
        reservation = services.manual_checkin(get_object_or_404(self.get_queryset(), pk=pk), by=request.user)
        return Response(self.get_serializer(reservation).data)

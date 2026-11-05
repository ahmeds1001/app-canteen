import csv
from datetime import timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core import audit, clock
from apps.core.models import AuditLog
from apps.core.permissions import IsCashierOrManagement, IsChefOrManagement, role_permission
from apps.reservations.serializers import DayReservationSerializer

from . import selectors

IsHROrManagement = role_permission("hr", "management")


def _period(request):
    end = parse_date(request.query_params.get("to", "")) or clock.today()
    start = parse_date(request.query_params.get("from", "")) or end - timedelta(days=30)
    return start, end


def _csv(rows: list[dict], filename: str, request) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # BOM so Excel opens accents correctly
    if rows:
        writer = csv.DictWriter(response, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    audit.record(AuditLog.Action.DATA_EXPORT, actor=request.user, report=filename)
    return response


def _wants_csv(request) -> bool:
    # Not `?format=`: DRF reserves that name for its own renderers and answers 404 to "csv".
    return request.query_params.get("export") == "csv"


def _month(request) -> tuple[int, int]:
    """`?month=2026-11`, the current month by default."""
    value = request.query_params.get("month", "")
    try:
        year, month = (int(part) for part in value.split("-"))
        if 1 <= month <= 12:
            return year, month
    except ValueError:
        pass
    today = clock.today()
    return today.year, today.month


class DailySummaryView(APIView):
    permission_classes = [IsChefOrManagement]

    def get(self, request):
        start, end = _period(request)
        rows = selectors.daily_summary(start, end)
        if _wants_csv(request):
            return _csv(rows, f"daily_{start}_{end}.csv", request)
        return Response(rows)


class AttendanceView(APIView):
    permission_classes = [IsHROrManagement]

    def get(self, request):
        start, end = _period(request)
        rows = selectors.employee_attendance(start, end)
        if _wants_csv(request):
            return _csv(rows, f"attendance_{start}_{end}.csv", request)
        return Response(rows)


class MonthlyAttendanceView(APIView):
    """Management dashboard: attendance per employee for one month, reserved vs served (FR-22, FR-23)."""

    permission_classes = [IsHROrManagement]

    def get(self, request):
        year, month = _month(request)
        p = request.query_params
        report = selectors.monthly_attendance(year, month, department=p.get("department", ""),
                                              q=p.get("q", "").strip())
        if _wants_csv(request):
            return _csv([_csv_row(r) for r in report["rows"]], f"presence_{report['month']}.csv", request)
        return Response(report)


def _csv_row(r: dict) -> dict:
    return {
        "nom": r["name"], "matricule": r["employee_number"] or "", "departement": r["department"],
        "reserves": r["reserved"], "servis": r["served"], "absents": r["no_show"], "a_venir": r["pending"],
        "annules": r["cancelled"], "menu_1": r["menu_1"], "menu_2": r["menu_2"],
        "taux_absence": f"{r['no_show_rate'] * 100:.1f}%".replace(".", ","), "depense_tnd": r["spent"],
    }


class EmployeeMonthView(APIView):
    """One employee's days in the month (drill-down from the dashboard). No QR code is exposed."""

    permission_classes = [IsHROrManagement]

    def get(self, request, user_id: int):
        year, month = _month(request)
        user = get_object_or_404(User, pk=user_id)
        rows = selectors.employee_month(user, year, month)
        return Response({"name": user.full_name, "employee_number": user.employee_number,
                         "rows": DayReservationSerializer(rows, many=True).data})


class CashView(APIView):
    """Money received on a day (FR-45): the cashier's own top-ups today, or every cashier on any day for
    management. `?date=YYYY-MM-DD` (management only), `?export=csv`."""

    permission_classes = [IsCashierOrManagement]

    def get(self, request):
        report = selectors.cash_report(request.user, parse_date(request.query_params.get("date", "")))
        if _wants_csv(request):
            return _csv([_cash_csv_row(r) for r in report["rows"]], f"caisse_{report['date']}.csv", request)
        return Response(report)


def _cash_csv_row(r: dict) -> dict:
    return {
        "heure": timezone.localtime(parse_datetime(r["at"])).strftime("%H:%M"),
        "type": "recharge" if r["kind"] == "topup" else "correction",
        "employe": r["employee"], "matricule": r["employee_number"] or "",
        "montant_tnd": r["amount"].replace(".", ","), "enregistre_par": r["by"], "motif": r["note"],
    }

import csv
from datetime import timedelta

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit, clock
from apps.core.models import AuditLog
from apps.core.permissions import IsChefOrManagement, role_permission

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


class DailySummaryView(APIView):
    permission_classes = [IsChefOrManagement]

    def get(self, request):
        start, end = _period(request)
        rows = selectors.daily_summary(start, end)
        if request.query_params.get("format") == "csv":
            return _csv(rows, f"daily_{start}_{end}.csv", request)
        return Response(rows)


class AttendanceView(APIView):
    permission_classes = [IsHROrManagement]

    def get(self, request):
        start, end = _period(request)
        rows = selectors.employee_attendance(start, end)
        if request.query_params.get("format") == "csv":
            return _csv(rows, f"attendance_{start}_{end}.csv", request)
        return Response(rows)

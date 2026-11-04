import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { reportApi } from "@/api/endpoints";
import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { addDays, formatCompanyDateTime, formatDay, isoToday } from "@/utils/dates";
import "./staff.css";

/** FR-45 (decided 2026-11-04): money received at the canteen on a day. The scanner sees her own top-ups of
 *  today — the cash she hands over in the evening; management sees any day, per cashier, with corrections. */
export default function CashReportPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const toMessage = useErrorMessage();
  const { serverTime } = useServerTime();
  const mine = user?.role === "scanner";
  const today = serverTime?.slice(0, 10) ?? isoToday();
  const [picked, setPicked] = useState<string | null>(null);
  const day = mine ? today : picked ?? today;
  const [error, setError] = useState("");

  const report = useQuery({
    queryKey: ["wallet", "cash", mine ? "today" : day],
    queryFn: () => reportApi.cash(mine ? undefined : day),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
  const data = report.data;
  const time = (at: string) => formatCompanyDateTime(at, i18n.language).split(", ")[1];
  const exportCsv = () => reportApi.cashCsv(data?.date ?? day).catch((e) => setError(toMessage(e)));

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t(mine ? "cash.titleMine" : "cash.title")}</h1>
        <Button variant="ghost" className="btn--sm" onClick={exportCsv}>{t("dayList.export")}</Button>
      </div>
      <p className="muted">{t(mine ? "cash.helpMine" : "cash.help")}</p>

      {!mine && (
        <div className="day-nav">
          <Button className="btn--sm" variant="ghost" onClick={() => setPicked(addDays(day, -1))}>‹ {t("dayList.prev")}</Button>
          <Field label={t("dayList.date")} type="date" value={day} onChange={(e) => e.target.value && setPicked(e.target.value)} />
          <Button className="btn--sm" variant="ghost" onClick={() => setPicked(null)} disabled={day === today}>
            {t("dayList.today")}
          </Button>
          <Button className="btn--sm" variant="ghost" onClick={() => setPicked(addDays(day, 1))} disabled={day >= today}>
            {t("dayList.next")} ›
          </Button>
        </div>
      )}
      <h2 className="day-nav__label">{formatDay(day, i18n.language)}</h2>
      {error && <Alert>{error}</Alert>}

      {data && (
        <Card className="day-summary">
          <div className="cash-total">
            <span className="day-summary__label">{t(mine ? "cash.toHandOver" : "cash.total")}</span>
            <span className="cash-total__value">{data.total} TND</span>
          </div>
          <div className="day-summary__counts">
            <Count value={data.topups.count} label={t("cash.topups")} />
            <Count value={`${data.topups.total} TND`} label={t("cash.received")} />
            {data.corrections.count > 0 && <Count value={`${data.corrections.total} TND`} label={t("cash.corrections", { count: data.corrections.count })} />}
          </div>
          {!mine && data.cashiers.length > 0 && (
            <div className="stack cash-cashiers">
              <strong>{t("cash.perCashier")}</strong>
              {data.cashiers.map((c) => (
                <p key={c.id ?? "none"} className="day-summary__menu">
                  {c.name} — <strong>{c.total} TND</strong>
                  <span className="muted"> ({t("cash.topupsN", { count: c.count })})</span>
                </p>
              ))}
            </div>
          )}
        </Card>
      )}

      {data && data.rows.length === 0 && <p className="muted">{t("cash.empty")}</p>}
      {data && data.rows.length > 0 && (
        <div className="day-table" role="table" aria-label={t(mine ? "cash.titleMine" : "cash.title")}>
          {data.rows.map((r) => (
            <div key={r.id} className="day-row" role="row">
              <span className="day-row__who" role="cell">
                <strong>{r.employee}</strong>
                <span className="muted">
                  {r.employee_number ?? "—"}
                  {!mine && r.by && ` · ${t("cash.by", { name: r.by })}`}
                  {r.note && ` · ${r.note}`}
                </span>
              </span>
              <span role="cell">
                {r.kind === "correction" && <Badge tone="orange">{t("cash.correction")}</Badge>}
              </span>
              <span role="cell"><strong>{r.amount} TND</strong></span>
              <span className="day-row__when muted" role="cell">{time(r.at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Count({ value, label }: { value: number | string; label: string }) {
  return (
    <div>
      <span className="day-summary__value">{value}</span>
      <span className="day-summary__label">{label}</span>
    </div>
  );
}

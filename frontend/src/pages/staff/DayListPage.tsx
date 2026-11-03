import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { dayListApi } from "@/api/endpoints";
import type { ReservationStatus } from "@/api/types";
import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { addDays, formatCompanyDateTime, formatDay, isoToday } from "@/utils/dates";
import "./staff.css";

const FILTERS: ("" | ReservationStatus)[] = ["", "reserved", "served", "no_show", "cancelled"];
const TONE: Record<ReservationStatus, "green" | "orange" | "red" | undefined> = {
  reserved: "orange", served: "green", no_show: "red", cancelled: undefined,
};

/** Decided 2026-11-03: the scanner and management see who reserved each day, past, today and future. */
export default function DayListPage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const { serverTime } = useServerTime();
  const today = serverTime?.slice(0, 10) ?? isoToday();
  const [picked, setPicked] = useState<string | null>(null);
  const day = picked ?? today;
  const [status, setStatus] = useState<"" | ReservationStatus>("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  const list = useQuery({
    queryKey: ["day-list", day, status, q],
    queryFn: () => dayListApi.get(day, { status, q: q.trim() }),
    placeholderData: keepPreviousData,
  });
  const data = list.data;
  const twoMenus = (data?.menu?.choices.length ?? 0) > 1;

  const exportCsv = () => dayListApi.exportCsv(day).catch((e) => setError(toMessage(e)));

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("dayList.title")}</h1>
        <Button variant="ghost" className="btn--sm" onClick={exportCsv}>{t("dayList.export")}</Button>
      </div>

      <div className="day-nav">
        <Button className="btn--sm" variant="ghost" onClick={() => setPicked(addDays(day, -1))}>‹ {t("dayList.prev")}</Button>
        <Field label={t("dayList.date")} type="date" value={day} onChange={(e) => e.target.value && setPicked(e.target.value)} />
        <Button className="btn--sm" variant="ghost" onClick={() => setPicked(null)} disabled={day === today}>
          {t("dayList.today")}
        </Button>
        <Button className="btn--sm" variant="ghost" onClick={() => setPicked(addDays(day, 1))}>{t("dayList.next")} ›</Button>
      </div>
      <h2 className="day-nav__label">{formatDay(day, i18n.language)}</h2>
      {error && <Alert>{error}</Alert>}

      {data && !data.menu && <p className="muted">{t("dayList.noMenu")}</p>}
      {data?.menu && (
        <Card className="day-summary">
          <div className="day-summary__counts">
            <Count value={data.counts.total} label={t("dayList.total")} />
            <Count value={data.counts.served} label={t("reservations.status.served")} />
            <Count value={data.counts.reserved} label={t("dayList.waiting")} />
            <Count value={data.counts.no_show} label={t("reservations.status.no_show")} />
            <Count value={data.counts.cancelled} label={t("reservations.status.cancelled")} />
            {data.menu.final_plate_count !== null && <Count value={data.menu.final_plate_count} label={t("finalize.plates")} />}
          </div>
          {data.menu.choices.map((c) => (
            <p key={c.choice} className="day-summary__menu">
              <strong>{twoMenus ? t("menus.menuN", { n: c.choice }) : t("dayList.menu")}</strong>
              {" — "}{c.dishes.length ? c.dishes.join(" · ") : t("menus.toBeAnnounced")}
              {twoMenus && <span className="muted"> ({t("dayList.reservedN", { count: c.reserved })})</span>}
            </p>
          ))}
          {data.menu.price && <Badge tone="orange">{t("menus.price", { price: data.menu.price })}</Badge>}
        </Card>
      )}

      <div className="tabs" role="tablist">
        {FILTERS.map((f) => (
          <button key={f || "all"} type="button" role="tab" aria-selected={status === f}
            className={`tab ${status === f ? "tab--active" : ""}`} onClick={() => setStatus(f)}>
            {f ? t(`reservations.status.${f}`) : t("dayList.all")}
          </button>
        ))}
      </div>
      <Field label={t("dayList.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} />

      {data && data.rows.length === 0 && <p className="muted">{t("dayList.empty")}</p>}
      {data && data.rows.length > 0 && (
        <div className="day-table" role="table" aria-label={t("dayList.title")}>
          {data.rows.map((r) => (
            <div key={r.id} className="day-row" role="row">
              <span className="day-row__who" role="cell">
                <strong>{r.full_name}</strong>
                <span className="muted">{r.employee_number ?? "—"}{r.department && ` · ${r.department}`}</span>
              </span>
              {twoMenus && <span role="cell"><Badge tone="orange">{t("menus.menuN", { n: r.choice })}</Badge></span>}
              <span role="cell"><Badge tone={TONE[r.status]}>{t(`reservations.status.${r.status}`)}</Badge></span>
              <span className="day-row__when muted" role="cell">
                {r.served_at
                  ? `${formatCompanyDateTime(r.served_at, i18n.language).split(", ")[1]}${r.scan_method === "manual" ? ` · ${t("dayList.manual")}` : ""}`
                  : r.payment_status === "paid" ? `${r.amount_due} TND` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Count({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <span className="day-summary__value">{value}</span>
      <span className="day-summary__label">{label}</span>
    </div>
  );
}

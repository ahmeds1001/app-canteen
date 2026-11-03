import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { reportApi } from "@/api/endpoints";
import type { AttendanceRow, ReservationStatus } from "@/api/types";
import { Alert, Badge, Button, Card, Dialog, Field, SelectField } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { formatDay, isoToday } from "@/utils/dates";
import "@/pages/employee/employee.css"; // ledger list (employee's days)
import "@/pages/staff/staff.css"; // month navigation and totals card, shared with the day list
import "./management.css";

type SortKey = "name" | "reserved" | "served" | "no_show" | "pending" | "cancelled" | "no_show_rate" | "spent";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "reserved", label: "attendance.reserved" },
  { key: "served", label: "attendance.served" },
  { key: "no_show", label: "attendance.noShow" },
  { key: "pending", label: "attendance.pending" },
  { key: "cancelled", label: "attendance.cancelled" },
  { key: "no_show_rate", label: "attendance.rate" },
  { key: "spent", label: "attendance.spent" },
];

const STATUS_TONE: Record<ReservationStatus, "green" | "orange" | "red" | undefined> = {
  reserved: "orange", served: "green", no_show: "red", cancelled: undefined,
};

function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonth(month: string, locale: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(new Date(y, m - 1, 1));
}

const percent = (rate: number) => `${Math.round(rate * 1000) / 10} %`;

/** Management dashboard (FR-22, FR-23): attendance per employee for a month, reserved vs served.
 *  Absences count only once the day is over; reservations still to be served are "pending". */
export default function AttendancePage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const { serverTime } = useServerTime();
  const thisMonth = (serverTime ?? isoToday()).slice(0, 7);
  const [picked, setPicked] = useState<string | null>(null);
  const month = picked ?? thisMonth;
  const [department, setDepartment] = useState("");
  const [q, setQ] = useState("");
  const [onlyEating, setOnlyEating] = useState(true);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "name", desc: false });
  const [open, setOpen] = useState<AttendanceRow | null>(null);
  const [error, setError] = useState("");

  const report = useQuery({
    queryKey: ["attendance", month, department, q],
    queryFn: () => reportApi.monthly(month, { department, q: q.trim() }),
    placeholderData: keepPreviousData,
  });
  const data = report.data;

  const value = (r: AttendanceRow, key: SortKey) => (key === "spent" ? Number(r.spent) : r[key]);
  const rows = (data?.rows ?? [])
    .filter((r) => !onlyEating || r.reserved > 0 || r.cancelled > 0)
    .sort((a, b) => {
      const [x, y] = [value(a, sort.key), value(b, sort.key)];
      const order = typeof x === "string" ? x.localeCompare(String(y), i18n.language) : Number(x) - Number(y);
      return sort.desc ? -order : order;
    });
  const sortBy = (key: SortKey) =>
    setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== "name" }));
  const arrow = (key: SortKey) => (sort.key === key ? (sort.desc ? " ↓" : " ↑") : "");

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("attendance.title")}</h1>
        <Button variant="ghost" className="btn--sm"
          onClick={() => reportApi.exportCsv(month).catch((e) => setError(toMessage(e)))}>
          {t("dayList.export")}
        </Button>
      </div>
      <p className="muted">{t("attendance.help")}</p>

      <div className="day-nav">
        <Button className="btn--sm" variant="ghost" onClick={() => setPicked(shiftMonth(month, -1))}>
          ‹ {t("attendance.prevMonth")}
        </Button>
        <Field label={t("attendance.month")} type="month" value={month}
          onChange={(e) => e.target.value && setPicked(e.target.value)} />
        <Button className="btn--sm" variant="ghost" onClick={() => setPicked(null)} disabled={month === thisMonth}>
          {t("attendance.thisMonth")}
        </Button>
        <Button className="btn--sm" variant="ghost" onClick={() => setPicked(shiftMonth(month, 1))}>
          {t("attendance.nextMonth")} ›
        </Button>
      </div>
      <h2 className="attendance__month">{formatMonth(month, i18n.language)}</h2>
      {error && <Alert>{error}</Alert>}

      {data && (
        <Card className="day-summary">
          <div className="day-summary__counts">
            <Total value={data.totals.eating} label={t("attendance.eating", { total: data.totals.employees })} />
            <Total value={data.totals.reserved} label={t("attendance.reserved")} />
            <Total value={data.totals.served} label={t("attendance.served")} />
            <Total value={data.totals.no_show} label={t("attendance.noShow")} />
            <Total value={data.totals.pending} label={t("attendance.pending")} />
            <Total value={data.totals.cancelled} label={t("attendance.cancelled")} />
            <Total value={percent(data.totals.no_show_rate)} label={t("attendance.rate")} />
            <Total value={`${data.totals.spent} TND`} label={t("attendance.spent")} />
          </div>
          {(data.totals.menu_2 > 0) && (
            <p className="day-summary__menu">
              {t("attendance.menuSplit", { m1: data.totals.menu_1, m2: data.totals.menu_2 })}
            </p>
          )}
          {data.totals.over_threshold > 0 && (
            <Badge tone="red">{t("attendance.overThreshold", { count: data.totals.over_threshold, n: data.threshold })}</Badge>
          )}
        </Card>
      )}

      <div className="toolbar">
        <SelectField label={t("attendance.department")} value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">{t("attendance.allDepartments")}</option>
          {data?.departments.map((d) => <option key={d} value={d}>{d}</option>)}
        </SelectField>
        <Field label={t("dayList.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="attendance__toggle">
          <input type="checkbox" checked={onlyEating} onChange={(e) => setOnlyEating(e.target.checked)} />
          {t("attendance.onlyEating")}
        </label>
      </div>

      {data && rows.length === 0 && <p className="muted">{t("attendance.empty")}</p>}
      {rows.length > 0 && (
        <div className="attendance__scroll">
          <table className="attendance">
            <thead>
              <tr>
                <th><button type="button" onClick={() => sortBy("name")}>{t("attendance.employee")}{arrow("name")}</button></th>
                {COLUMNS.map((c) => (
                  <th key={c.key} className="num">
                    <button type="button" onClick={() => sortBy(c.key)}>{t(c.label)}{arrow(c.key)}</button>
                  </th>
                ))}
                {(data?.totals.menu_2 ?? 0) > 0 && <th className="num">{t("attendance.menus")}</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.user_id} className={r.over_threshold ? "attendance__alert" : ""} onClick={() => setOpen(r)}>
                  <td>
                    <button type="button" className="attendance__who">
                      <strong>{r.name}</strong>
                      <span className="muted">{r.employee_number ?? "—"}{r.department && ` · ${r.department}`}</span>
                    </button>
                  </td>
                  <td className="num">{r.reserved}</td>
                  <td className="num">{r.served}</td>
                  <td className="num">{r.no_show > 0 ? <Badge tone="red">{r.no_show}</Badge> : 0}</td>
                  <td className="num">{r.pending}</td>
                  <td className="num">{r.cancelled}</td>
                  <td className="num">{r.served + r.no_show > 0 ? percent(r.no_show_rate) : "—"}</td>
                  <td className="num">{r.spent}</td>
                  {(data?.totals.menu_2 ?? 0) > 0 && <td className="num">{r.menu_1} / {r.menu_2}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && <EmployeeDialog row={open} month={month} today={(serverTime ?? isoToday()).slice(0, 10)} onClose={() => setOpen(null)} />}
    </div>
  );
}

function Total({ value, label }: { value: number | string; label: string }) {
  return (
    <div>
      <span className="day-summary__value">{value}</span>
      <span className="day-summary__label">{label}</span>
    </div>
  );
}

/** One employee's days in the month. */
function EmployeeDialog({ row, month, today, onClose }: {
  row: AttendanceRow;
  month: string;
  today: string;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const days = useQuery({ queryKey: ["attendance", "employee", row.user_id, month], queryFn: () => reportApi.employee(row.user_id, month) });
  return (
    <Dialog title={`${row.name} — ${formatMonth(month, i18n.language)}`} onClose={onClose} wide>
      <div className="stack">
        <p className="muted">
          {t("attendance.summary", { reserved: row.reserved, served: row.served, noShow: row.no_show, spent: row.spent })}
        </p>
        {days.data?.rows.length === 0 && <p className="muted">{t("attendance.noDays")}</p>}
        <ul className="ledger">
          {days.data?.rows.map((d) => (
            <li key={d.id}>
              <span className="ledger__what">
                <strong>{formatDay(d.date, i18n.language)}</strong>
                <span className="ledger__meta">
                  {t("menus.menuN", { n: d.choice })}{d.menu_items.length > 0 && ` · ${d.menu_items.join(" · ")}`}
                </span>
              </span>
              <span className="ledger__amount">
                <Badge tone={STATUS_TONE[d.status]}>
                  {/* Same wording as the day list: a future day is "reserved", a started one "not served yet". */}
                  {d.status === "reserved" && d.date <= today ? t("dayList.notServedYet") : t(`reservations.status.${d.status}`)}
                </Badge>
                <br />
                <span className="ledger__meta">
                  {d.served_at ? d.served_at.slice(11, 16) : ""}
                  {d.payment_status === "paid" && ` ${d.amount_due} TND`}
                  {d.payment_status === "refunded" && ` ${t("reservations.payment.refunded")}`}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Dialog>
  );
}

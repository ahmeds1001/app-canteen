import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { settingsApi } from "@/api/endpoints";
import type { AdminSettings } from "@/api/types";
import { Alert, Button, Card, Field, SelectField } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { addDays, formatDay, isoToday, weekdayIndex } from "@/utils/dates";
import "./admin.css";

type Form = AdminSettings;
const TIME_FIELDS = [
  "cutoff_time", "publish_deadline_time", "finalization_deadline", "service_window_start", "service_window_end",
  "menu_missing_reminder_time", "finalization_reminder_time", "evening_reminder_time",
] as const;
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
const hhmm = (time: string) => time.slice(0, 5);

/** Only the values the admin changed (times compared as HH:MM, so an untouched 23:59:59 stays as it is). */
function changes(saved: Form, form: Form): Partial<Form> {
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(form) as (keyof Form)[]) {
    const before = saved[key];
    const after = form[key];
    const same = (TIME_FIELDS as readonly string[]).includes(key)
      ? hhmm(String(before)) === hhmm(String(after))
      : before === after;
    if (!same) out[key] = after;
  }
  return out as Partial<Form>;
}

/** FR-46 (decided 2026-11-04): the admin sets every deadline and canteen parameter. Applies at once. */
export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const { serverTime } = useServerTime();
  const settings = useQuery({ queryKey: ["admin-settings"], queryFn: settingsApi.get });
  const [form, setForm] = useState<Form | null>(null);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);

  const save = useMutation({
    mutationFn: (diff: Partial<Form>) => settingsApi.update(diff),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-settings"], data);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setMessage({ kind: "success", text: t("settings.saved") });
    },
    onError: (e) => setMessage({ kind: "error", text: toMessage(e) }),
  });

  const diff = settings.data && form ? changes(settings.data, form) : {};
  const dirty = Object.keys(diff).length > 0;

  // A concrete example: the first service day a week from now, with every deadline worked out.
  const example = useMemo(() => {
    if (!form) return null;
    const days = form.service_weekdays.split(",").filter(Boolean).map(Number);
    let day = addDays(serverTime?.slice(0, 10) ?? isoToday(), 7);
    for (let i = 0; i < 7 && !days.includes(weekdayIndex(day)); i++) day = addDays(day, 1);
    const at = (daysBefore: number, time: string) =>
      t("settings.example.at", { day: formatDay(addDays(day, -daysBefore), i18n.language), time: hhmm(time) });
    return {
      day: formatDay(day, i18n.language),
      publish: at(form.publish_deadline_days, form.publish_deadline_time),
      cutoff: at(form.cutoff_days, form.cutoff_time),
      finalize: at(0, form.finalization_deadline),
      service: t("settings.example.service", { start: hhmm(form.service_window_start), end: hhmm(form.service_window_end) }),
    };
  }, [form, serverTime, t, i18n.language]);

  if (!form) {
    return <div className="container">{settings.error ? <Alert>{toMessage(settings.error)}</Alert> : null}</div>;
  }

  const set = <K extends keyof Form>(key: K, value: Form[K]) => {
    setMessage(null);
    setForm({ ...form, [key]: value });
  };
  const num = (key: "cutoff_days" | "publish_deadline_days" | "buffer_value" | "no_show_warning_threshold") =>
    (e: React.ChangeEvent<HTMLInputElement>) => set(key, Number(e.target.value));
  const optionalNum = (key: "kitchen_max_plates" | "booking_horizon_days") =>
    (e: React.ChangeEvent<HTMLInputElement>) => set(key, e.target.value === "" ? null : Number(e.target.value));
  const time = (key: (typeof TIME_FIELDS)[number]) => ({
    type: "time",
    value: hhmm(form[key]),
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => e.target.value && set(key, e.target.value),
  });
  const weekdays = form.service_weekdays.split(",").filter(Boolean).map(Number);
  const toggleDay = (d: number) => {
    const next = weekdays.includes(d) ? weekdays.filter((x) => x !== d) : [...weekdays, d];
    set("service_weekdays", next.sort().join(","));
  };

  return (
    <div className="container stack settings">
      <div className="page-head">
        <h1>{t("settings.title")}</h1>
      </div>
      <p className="muted">{t("settings.help")}</p>

      <Card>
        <h2>{t("settings.deadlines")}</h2>
        <Deadline label={t("settings.cutoff")} hint={t("settings.cutoffHint")}>
          <Field label={t("settings.daysBefore")} type="number" min={0} max={7} value={form.cutoff_days}
            onChange={num("cutoff_days")} />
          <Field label={t("settings.time")} {...time("cutoff_time")} />
        </Deadline>
        <Deadline label={t("settings.publish")} hint={t("settings.publishHint")}>
          <Field label={t("settings.daysBefore")} type="number" min={1} max={14} value={form.publish_deadline_days}
            onChange={num("publish_deadline_days")} />
          <Field label={t("settings.time")} {...time("publish_deadline_time")} />
        </Deadline>
        <Deadline label={t("settings.finalization")} hint={t("settings.finalizationHint")}>
          <Field label={t("settings.sameDay")} {...time("finalization_deadline")} />
        </Deadline>
        <Deadline label={t("settings.service")}>
          <Field label={t("settings.from")} {...time("service_window_start")} />
          <Field label={t("settings.to")} {...time("service_window_end")} />
        </Deadline>
        {example && (
          <div className="settings__example" aria-live="polite">
            <strong>{t("settings.example.title", { day: example.day })}</strong>
            <ul>
              <li>{t("settings.example.publish")} : {example.publish}</li>
              <li>{t("settings.example.cutoff")} : {example.cutoff}</li>
              <li>{t("settings.example.finalize")} : {example.finalize}</li>
              <li>{t("settings.example.serviceLabel")} : {example.service}</li>
            </ul>
          </div>
        )}
      </Card>

      <Card>
        <h2>{t("settings.days")}</h2>
        <div className="settings__days">
          {WEEKDAYS.map((d) => (
            <label key={d} className="check">
              <input type="checkbox" checked={weekdays.includes(d)} onChange={() => toggleDay(d)} />
              {t(`settings.weekday.${d}`)}
            </label>
          ))}
        </div>
      </Card>

      <Card>
        <h2>{t("settings.reminders")}</h2>
        <div className="settings__row">
          <Field label={t("settings.reminderChef")} {...time("menu_missing_reminder_time")} />
          <Field label={t("settings.reminderManagement")} {...time("finalization_reminder_time")} />
          <Field label={t("settings.reminderEmployees")} {...time("evening_reminder_time")} />
        </div>
        <p className="muted settings__hint">{t("settings.remindersHint")}</p>
      </Card>

      <Card>
        <h2>{t("settings.plates")}</h2>
        <div className="settings__row">
          <SelectField label={t("settings.bufferMode")} value={form.buffer_mode}
            onChange={(e) => set("buffer_mode", e.target.value as Form["buffer_mode"])}>
            <option value="percentage">{t("settings.bufferPercentage")}</option>
            <option value="fixed">{t("settings.bufferFixed")}</option>
          </SelectField>
          <Field label={t(form.buffer_mode === "percentage" ? "settings.bufferPercent" : "settings.bufferPlates")}
            type="number" min={0} max={form.buffer_mode === "percentage" ? 100 : 500} value={form.buffer_value}
            onChange={num("buffer_value")} />
          <Field label={t("settings.kitchenMax")} type="number" min={1} placeholder={t("settings.noLimit")}
            value={form.kitchen_max_plates ?? ""} onChange={optionalNum("kitchen_max_plates")} />
        </div>
        <p className="muted settings__hint">{t("settings.bufferHint")}</p>
      </Card>

      <Card>
        <h2>{t("settings.payment")}</h2>
        <div className="settings__row">
          <label className="check">
            <input type="checkbox" checked={form.payment_enabled} onChange={(e) => set("payment_enabled", e.target.checked)} />
            {t("settings.paymentEnabled")}
          </label>
          <label className="check">
            <input type="checkbox" checked={form.meal_paid_default} disabled={!form.payment_enabled}
              onChange={(e) => set("meal_paid_default", e.target.checked)} />
            {t("settings.paidDefault")}
          </label>
          <Field label={t("settings.priceDefault", { currency: form.currency })} type="number" min={0} max={1000}
            step="0.001" value={form.meal_price_default} disabled={!form.payment_enabled}
            onChange={(e) => set("meal_price_default", e.target.value)} />
        </div>
      </Card>

      <Card>
        <h2>{t("settings.other")}</h2>
        <div className="settings__row">
          <Field label={t("settings.horizon")} type="number" min={1} max={365} placeholder={t("settings.noLimit")}
            value={form.booking_horizon_days ?? ""} onChange={optionalNum("booking_horizon_days")} />
          <Field label={t("settings.noShowThreshold")} type="number" min={1} max={31}
            value={form.no_show_warning_threshold} onChange={num("no_show_warning_threshold")} />
          <Field label={t("settings.noShowGrace")} type="date" value={form.no_show_grace_until ?? ""}
            onChange={(e) => set("no_show_grace_until", e.target.value || null)} />
        </div>
      </Card>

      <div className="settings__bar">
        {message && <Alert kind={message.kind}>{message.text}</Alert>}
        <div className="actions">
          <Button variant="ghost" disabled={!dirty || save.isPending}
            onClick={() => { setForm(settings.data!); setMessage(null); }}>
            {t("common.cancel")}
          </Button>
          <Button disabled={!dirty || save.isPending} onClick={() => save.mutate(diff)}>
            {dirty ? t("settings.save", { count: Object.keys(diff).length }) : t("common.save")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Deadline({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="settings__deadline">
      <div>
        <strong>{label}</strong>
        {hint && <p className="muted settings__hint">{hint}</p>}
      </div>
      <div className="settings__row">{children}</div>
    </div>
  );
}

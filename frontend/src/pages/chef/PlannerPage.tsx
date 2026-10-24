import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { dishApi, menuApi, settingsApi } from "@/api/endpoints";
import { DISH_CATEGORIES, type Dish, type StaffMenu } from "@/api/types";
import { Alert, Badge, Button, Card, Dialog, Field, SelectField } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { addDays, formatDay, formatShortDate, isoToday, startOfWeek, weekdayIndex } from "@/utils/dates";
import { DishFormDialog } from "./DishFormDialog";
import "./chef.css";

const STATUS_TONE: Record<string, "green" | "orange" | "red" | undefined> = {
  draft: "orange", published: "green", locked: undefined, finalized: undefined, closed: "red",
};

/** The chef's dish ids can be changed while the day is draft/published (backend checks the cutoff),
 *  or while an empty placeholder still waits for its dishes (FR-38). */
function canEditDishes(menu?: StaffMenu): boolean {
  if (!menu) return true;
  if (menu.status === "draft" || menu.status === "published") return true;
  return menu.is_placeholder && menu.items.length === 0 && (menu.status === "locked" || menu.status === "finalized");
}

function defaultWeek(): string {
  const today = isoToday();
  // On the weekend, plan the coming week.
  return weekdayIndex(today) >= 5 ? startOfWeek(addDays(today, 7)) : startOfWeek(today);
}

type Picking = { date: string; menu?: StaffMenu };

/** FR-07, FR-09, FR-10, FR-38: plan a week, pick dishes, publish, duplicate, close a day. */
export default function PlannerPage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(defaultWeek);
  const [picking, setPicking] = useState<Picking | null>(null);
  const [duplicating, setDuplicating] = useState<string | null>(null);
  const [closing, setClosing] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  const weekEnd = addDays(weekStart, 6);
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.public, staleTime: Infinity });
  const menus = useQuery({
    queryKey: ["menus", "staff", weekStart],
    queryFn: () => menuApi.staffList(weekStart, weekEnd),
  });

  const serviceDays = settings.data?.service_weekdays.split(",").map((d) => Number(d.trim())) ?? [0, 1, 2, 3, 4];
  const deadlineDays = settings.data?.publish_deadline_days ?? 2;
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)).filter((d) =>
    serviceDays.includes(weekdayIndex(d)),
  );
  const byDate = new Map((menus.data ?? []).map((m) => [m.date, m]));

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["menus"] });
  const fail = (e: unknown) => setMessage({ kind: "error", text: toMessage(e) });

  const publish = useMutation({
    mutationFn: menuApi.publish,
    onSuccess: () => { setMessage(null); refresh(); },
    onError: fail,
  });
  const publishWeek = useMutation({
    mutationFn: async (dates: string[]) => {
      for (const date of dates) await menuApi.publish(date);
      return dates.length;
    },
    onSuccess: (count) => { setMessage({ kind: "success", text: t("planner.weekPublished", { count }) }); refresh(); },
    onError: (e) => { fail(e); refresh(); },
  });

  const publishable = days.filter((d) => {
    const m = byDate.get(d);
    return m?.status === "draft" && m.items.length > 0;
  });

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("planner.title")}</h1>
        <div className="week-nav">
          <Button className="btn--sm" variant="ghost" onClick={() => setWeekStart(addDays(weekStart, -7))}>
            ‹ {t("planner.prevWeek")}
          </Button>
          <span className="week-nav__label">
            {t("planner.weekOf", { date: formatShortDate(weekStart, i18n.language) })}
          </span>
          <Button className="btn--sm" variant="ghost" onClick={() => setWeekStart(addDays(weekStart, 7))}>
            {t("planner.nextWeek")} ›
          </Button>
        </div>
      </div>
      <p className="muted">{t("planner.help", { days: deadlineDays })}</p>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}
      {publishable.length > 0 && (
        <div>
          <Button disabled={publishWeek.isPending} onClick={() => publishWeek.mutate(publishable)}>
            {t("planner.publishWeek", { count: publishable.length })}
          </Button>
        </div>
      )}
      <div className="plan-grid">
        {days.map((date) => {
          const menu = byDate.get(date);
          const status = menu?.status;
          const deadline = addDays(date, -deadlineDays);
          return (
            <Card key={date} className={`plan-day ${status === "closed" ? "plan-day--closed" : ""}`}>
              <div className="plan-day__head">
                <span className="plan-day__date">{formatDay(date, i18n.language)}</span>
                <Badge tone={status ? STATUS_TONE[status] : undefined}>
                  {t(`planner.status.${status ?? "none"}`)}
                </Badge>
              </div>
              {menu?.is_placeholder && <Badge tone="orange">{t("planner.placeholder")}</Badge>}
              {menu && menu.items.length > 0 ? (
                <ul className="plan-day__items">
                  {menu.items.map((item) => (
                    <li key={item.id}>
                      <span>{item.name}</span>
                      <span>{t(`dishes.categories.${item.category}`)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                status !== "closed" && <p className="plan-day__empty">{t("planner.noDishes")}</p>
              )}
              {status === "closed" && menu?.closed_reason && (
                <p className="plan-day__hint">{t("planner.closedReason", { reason: menu.closed_reason })}</p>
              )}
              {(!status || status === "draft") && (
                <p className="plan-day__hint">
                  {t("planner.publishBefore", { date: formatShortDate(deadline, i18n.language) })}
                </p>
              )}
              {menu && status !== "draft" && status !== "closed" && (
                <p className="plan-day__hint">{t("planner.reservedCount", { count: menu.reserved_count })}</p>
              )}
              <div className="actions">
                {canEditDishes(menu) && status !== "closed" && (
                  <Button className="btn--sm" variant="ghost" onClick={() => setPicking({ date, menu })}>
                    {t(menu && menu.items.length > 0 ? "planner.editDishes" : "planner.compose")}
                  </Button>
                )}
                {(!status || status === "draft" || status === "published") && (
                  <Button className="btn--sm" variant="ghost" onClick={() => setDuplicating(date)}>
                    {t("planner.duplicate")}
                  </Button>
                )}
                {status === "draft" && (
                  <Button
                    className="btn--sm"
                    disabled={publish.isPending || menu!.items.length === 0}
                    onClick={() => publish.mutate(date)}
                  >
                    {t("planner.publish")}
                  </Button>
                )}
                {(!status || status === "draft" || status === "published") && (
                  <Button className="btn--sm" variant="danger" onClick={() => setClosing(date)}>
                    {t("planner.closeDay")}
                  </Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {picking && (
        <DishPickerDialog
          date={picking.date}
          menu={picking.menu}
          onClose={() => setPicking(null)}
          onSaved={() => { setMessage(null); refresh(); }}
        />
      )}
      {duplicating && (
        <DuplicateDialog
          date={duplicating}
          onClose={() => setDuplicating(null)}
          onDone={(skipped) => {
            setMessage(skipped ? { kind: "success", text: t("planner.duplicateSkipped", { count: skipped }) } : null);
            refresh();
          }}
        />
      )}
      {closing && (
        <CloseDayDialog date={closing} onClose={() => setClosing(null)} onDone={() => { setMessage(null); refresh(); }} />
      )}
    </div>
  );
}

/** Save dishes for a day: the menu is created as a draft if needed (idempotent on the backend). */
async function saveDishes(date: string, dishIds: number[]) {
  await menuApi.create(date);
  return menuApi.setItems(date, dishIds);
}

function DishPickerDialog({ date, menu, onClose, onSaved }: {
  date: string;
  menu?: StaffMenu;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [selected, setSelected] = useState<number[]>(
    () => (menu?.items ?? []).map((i) => i.dish).filter((id): id is number => id !== null),
  );
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const dishes = useQuery({ queryKey: ["dishes", { all: true }], queryFn: () => dishApi.list() });
  const byId = new Map((dishes.data ?? []).map((d) => [d.id, d]));
  const visible = (dishes.data ?? []).filter(
    (d) => (!category || d.category === category) && d.name.toLowerCase().includes(q.trim().toLowerCase()),
  );

  const save = useMutation({
    mutationFn: () => saveDishes(date, selected),
    onSuccess: () => { onSaved(); onClose(); },
    onError: (e) => setError(toMessage(e)),
  });

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <Dialog title={t("planner.pickTitle", { date: formatDay(date, i18n.language) })} onClose={onClose} wide>
      <div className="picker">
        {error && <Alert>{error}</Alert>}
        <div className="toolbar">
          <Field label={t("common.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
          <SelectField label={t("dishes.category")} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t("dishes.allCategories")}</option>
            {DISH_CATEGORIES.map((c) => (
              <option key={c} value={c}>{t(`dishes.categories.${c}`)}</option>
            ))}
          </SelectField>
          <Button type="button" variant="ghost" onClick={() => setCreating(true)}>{t("dishes.new")}</Button>
        </div>
        {dishes.data?.length === 0 && <p className="muted">{t("planner.libraryEmpty")}</p>}
        {visible.length > 0 && (
          <ul className="picker__list">
            {visible.map((dish) => (
              <li key={dish.id}>
                <label className="picker__row">
                  <input type="checkbox" checked={selected.includes(dish.id)} onChange={() => toggle(dish.id)} />
                  <span className="picker__name">{dish.name}</span>
                  <span className="picker__meta">
                    {t(`dishes.categories.${dish.category}`)}
                    <br />
                    {dish.last_served_on
                      ? t("dishes.lastServed", { date: formatShortDate(dish.last_served_on, i18n.language) })
                      : t("dishes.neverServed")}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <p className="picker__selected">
          <strong>{t("planner.selected", { count: selected.length })}</strong>{" "}
          {selected.map((id) => byId.get(id)?.name).filter(Boolean).join(" · ")}
        </p>
        <div className="actions">
          <Button disabled={save.isPending || selected.length === 0} onClick={() => save.mutate()}>
            {t("common.save")}
          </Button>
          <Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
        </div>
      </div>
      {creating && (
        <DishFormDialog
          onClose={() => setCreating(false)}
          onSaved={(dish: Dish) => setSelected((s) => [...s, dish.id])}
        />
      )}
    </Dialog>
  );
}

/** FR-09: copy the dishes of another day (archived dishes are skipped). */
function DuplicateDialog({ date, onClose, onDone }: {
  date: string;
  onClose: () => void;
  onDone: (skipped: number) => void;
}) {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const [source, setSource] = useState(addDays(date, -7));
  const [error, setError] = useState("");

  const copy = useMutation({
    mutationFn: async () => {
      const [menus, library] = await Promise.all([menuApi.staffList(source, source), dishApi.list()]);
      const items = menus[0]?.items ?? [];
      if (items.length === 0) throw new Error("source_empty");
      const available = new Set(library.map((d) => d.id));
      const ids = items.map((i) => i.dish).filter((id): id is number => id !== null && available.has(id));
      if (ids.length === 0) throw new Error("source_empty");
      await saveDishes(date, ids);
      return items.length - ids.length;
    },
    onSuccess: (skipped) => { onDone(skipped); onClose(); },
    onError: (e) => setError(e instanceof Error && e.message === "source_empty" ? t("planner.sourceEmpty") : toMessage(e)),
  });

  return (
    <Dialog title={t("planner.duplicateTitle", { date: formatDay(date, i18n.language) })} onClose={onClose}>
      <div className="stack">
        {error && <Alert>{error}</Alert>}
        <Field label={t("planner.sourceDay")} type="date" value={source} onChange={(e) => setSource(e.target.value)} />
        <div className="actions">
          <Button disabled={copy.isPending || !source} onClick={() => copy.mutate()}>{t("planner.duplicate")}</Button>
          <Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
        </div>
      </div>
    </Dialog>
  );
}

/** FR-10: close a day (holiday, maintenance). Its reservations are cancelled. */
function CloseDayDialog({ date, onClose, onDone }: { date: string; onClose: () => void; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const close = useMutation({
    mutationFn: async () => {
      await menuApi.create(date);
      return menuApi.close(date, reason);
    },
    onSuccess: () => { onDone(); onClose(); },
    onError: (e) => setError(toMessage(e)),
  });

  return (
    <Dialog title={t("planner.closeTitle", { date: formatDay(date, i18n.language) })} onClose={onClose}>
      <div className="stack">
        {error && <Alert>{error}</Alert>}
        <p className="muted">{t("planner.closeHelp")}</p>
        <Field label={t("planner.closeReason")} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={120} />
        <div className="actions">
          <Button variant="danger" disabled={close.isPending} onClick={() => close.mutate()}>{t("planner.closeDay")}</Button>
          <Button variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
        </div>
      </div>
    </Dialog>
  );
}

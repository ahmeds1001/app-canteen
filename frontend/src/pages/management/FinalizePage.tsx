import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { menuApi, settingsApi } from "@/api/endpoints";
import type { MenuChoice, PerMenu, StaffMenu } from "@/api/types";
import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { addDays, formatCompanyDateTime, formatDay, isoToday } from "@/utils/dates";
import "./management.css";

/** FR-24 to FR-28: after the cutoff, management confirms how many plates of each menu the kitchen
 *  prepares. Before the cutoff, it sets the day's price (FR-32), paid from the employees' balance. */
export default function FinalizePage() {
  const { t } = useTranslation();
  const { serverTime } = useServerTime();
  const today = serverTime?.slice(0, 10) ?? isoToday();
  const menus = useQuery({
    queryKey: ["menus", "staff", "finalize", today],
    queryFn: () => menuApi.staffList(today, addDays(today, 7)),
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.public, staleTime: Infinity });
  const days = menus.data ?? [];
  // FR-26/27: the count locks at the finalization deadline (10:00 by default), never after service start.
  const start = settings.data?.service_window_start ?? "12:00:00";
  const deadline = [settings.data?.finalization_deadline ?? "10:00:00", start].sort()[0];

  return (
    <div className="container stack">
      <h1>{t("finalize.title")}</h1>
      <p className="muted">{t("finalize.help", { time: deadline.slice(0, 5) })}</p>
      {settings.data && !settings.data.payment_enabled && <Alert kind="info">{t("finalize.paymentOff")}</Alert>}
      {menus.data && days.length === 0 && <p className="muted">{t("finalize.empty")}</p>}
      <div className="final-grid">
        {days.map((menu) => (
          <FinalizeCard
            key={menu.id}
            menu={menu}
            deadline={deadline}
            serverTime={serverTime}
            paymentEnabled={settings.data?.payment_enabled ?? false}
          />
        ))}
      </div>
    </div>
  );
}

function FinalizeCard({ menu, deadline, serverTime, paymentEnabled }: {
  menu: StaffMenu;
  deadline: string;
  serverTime?: string;
  paymentEnabled: boolean;
}) {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [counts, setCounts] = useState<PerMenu>({});
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  // The final count is locked at the finalization deadline (FR-27). Both strings are company
  // wall-clock time, so they compare as text; the backend enforces the rule anyway.
  const locked = Boolean(serverTime && serverTime.slice(0, 19) >= `${menu.date}T${deadline}`);
  const canFinalize = (menu.status === "locked" || (menu.status === "finalized" && editing)) && !locked;
  const beforeCutoff = (menu.status === "draft" || menu.status === "published")
    && Boolean(serverTime && serverTime.slice(0, 19) <= menu.reservation_cutoff.slice(0, 19));
  const twoMenus = menu.choices.length > 1;

  const proposal = useQuery({
    queryKey: ["finalization", menu.date],
    queryFn: () => menuApi.finalization(menu.date),
    enabled: canFinalize,
  });
  const valueFor = (choice: MenuChoice) =>
    counts[`${choice}`] ?? proposal.data?.choices.find((c) => c.choice === choice)?.proposed ?? "";
  const choices = proposal.data?.choices.map((c) => c.choice) ?? menu.choices;

  const finalize = useMutation({
    mutationFn: () => menuApi.finalize(menu.date, Object.fromEntries(choices.map((c) => [`${c}`, Number(valueFor(c))]))),
    onSuccess: () => {
      setEditing(false);
      setCounts({});
      setError("");
      queryClient.invalidateQueries({ queryKey: ["menus"] });
    },
    onError: (e) => setError(toMessage(e)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    finalize.mutate();
  };

  return (
    <Card className="final">
      <div className="final__head">
        <span className="final__date">{formatDay(menu.date, i18n.language)}</span>
        <Badge tone={menu.status === "finalized" ? "green" : menu.status === "locked" ? "orange" : undefined}>
          {t(`finalize.status.${menu.status}`)}
        </Badge>
      </div>
      <div className="final__numbers">
        <div>
          <span className="final__value">{menu.reserved_count}</span>
          <span className="final__label">{t("finalize.reserved")}</span>
        </div>
        {menu.final_plate_count !== null && (
          <div>
            <span className="final__value final__value--main">{menu.final_plate_count}</span>
            <span className="final__label">{t("finalize.plates")}</span>
          </div>
        )}
      </div>
      {twoMenus && (
        <ul className="final__split">
          {menu.choices.map((c) => (
            <li key={c}>
              <strong>{t("menus.menuN", { n: c })}</strong>
              <span>
                {t("finalize.splitReserved", { count: menu.reserved_by_choice[`${c}`] ?? 0 })}
                {menu.final_plates_by_choice[`${c}`] !== undefined &&
                  ` · ${t("finalize.splitPlates", { count: menu.final_plates_by_choice[`${c}`] })}`}
              </span>
            </li>
          ))}
        </ul>
      )}

      {menu.status === "published" && (
        <p className="final__hint">
          {t("finalize.waitCutoff", { date: formatCompanyDateTime(menu.reservation_cutoff, i18n.language) })}
        </p>
      )}
      {menu.status === "closed" && menu.closed_reason && (
        <p className="final__hint">{t("planner.closedReason", { reason: menu.closed_reason })}</p>
      )}
      {menu.final_plate_count !== null && (
        <p className="final__hint">
          {menu.auto_finalized ? t("finalize.auto") : t("finalize.buffer", { buffer: menu.buffer ?? 0 })}
        </p>
      )}

      {paymentEnabled && <PriceEditor menu={menu} editable={beforeCutoff} />}

      {error && <Alert>{error}</Alert>}
      {canFinalize && (
        <form className="stack" onSubmit={submit}>
          {proposal.data && (
            <p className="final__hint">
              {t("finalize.proposal", {
                reserved: proposal.data.reserved,
                buffer: proposal.data.buffer,
                proposed: proposal.data.proposed,
              })}
            </p>
          )}
          {choices.map((c) => (
            <Field
              key={c}
              label={twoMenus ? t("finalize.finalCountN", { n: c }) : t("finalize.finalCount")}
              type="number"
              inputMode="numeric"
              min={proposal.data?.choices.find((p) => p.choice === c)?.reserved ?? 0}
              value={String(valueFor(c))}
              onChange={(e) => setCounts((s) => ({ ...s, [`${c}`]: e.target.value === "" ? undefined : Number(e.target.value) }))}
              required
            />
          ))}
          <div className="actions">
            <Button type="submit" disabled={finalize.isPending || choices.some((c) => valueFor(c) === "")}>
              {t("finalize.confirm")}
            </Button>
            {editing && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>{t("common.cancel")}</Button>}
          </div>
        </form>
      )}
      {menu.status === "finalized" && !editing && !locked && (
        <div className="actions">
          <Button className="btn--sm" variant="ghost" onClick={() => setEditing(true)}>{t("finalize.change")}</Button>
        </div>
      )}
    </Card>
  );
}

/** FR-32: one price for the day (both menus), paid from the balance when reserving. Changeable until
 *  the cutoff; a new price only applies to reservations made after it. Empty or 0 = free day. */
function PriceEditor({ menu, editable }: { menu: StaffMenu; editable: boolean }) {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const current = menu.is_paid && menu.price ? menu.price : "";
  const [price, setPrice] = useState(current);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: () => {
      const paid = Number(price) > 0;
      return menuApi.setPrice(menu.date, paid, paid ? Number(price).toFixed(3) : null);
    },
    onSuccess: () => { setError(""); setSaved(true); queryClient.invalidateQueries({ queryKey: ["menus"] }); },
    onError: (e) => { setSaved(false); setError(toMessage(e)); },
  });

  if (!editable) {
    return (
      <p className="final__hint">
        {current ? t("finalize.priceIs", { price: current }) : t("finalize.priceFree")}
      </p>
    );
  }
  return (
    <form className="final__price" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <Field
        label={t("finalize.price")}
        type="number"
        inputMode="decimal"
        min={0}
        step="0.001"
        placeholder={t("finalize.priceFreePlaceholder")}
        value={price}
        onChange={(e) => { setSaved(false); setPrice(e.target.value); }}
      />
      <Button type="submit" className="btn--sm" variant="ghost" disabled={save.isPending || price === current}>
        {t("common.save")}
      </Button>
      {saved && <span className="final__ok">✓</span>}
      {error && <Alert>{error}</Alert>}
      <span className="final__hint">{t("finalize.priceHelp")}</span>
    </form>
  );
}

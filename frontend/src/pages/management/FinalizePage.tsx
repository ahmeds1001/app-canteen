import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { menuApi, settingsApi } from "@/api/endpoints";
import type { StaffMenu } from "@/api/types";
import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { addDays, formatCompanyDateTime, formatDay, isoToday } from "@/utils/dates";
import "./management.css";

/** FR-24 to FR-28: after the cutoff, management confirms how many plates the kitchen prepares. */
export default function FinalizePage() {
  const { t } = useTranslation();
  const { serverTime } = useServerTime();
  const today = serverTime?.slice(0, 10) ?? isoToday();
  const menus = useQuery({
    queryKey: ["menus", "staff", "finalize", today],
    queryFn: () => menuApi.staffList(today, addDays(today, 7)),
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.public, staleTime: Infinity });
  const days = (menus.data ?? []).filter((m) => m.status !== "draft");

  return (
    <div className="container stack">
      <h1>{t("finalize.title")}</h1>
      <p className="muted">
        {t("finalize.help", { time: settings.data?.service_window_start.slice(0, 5) ?? "12:00" })}
      </p>
      {menus.data && days.length === 0 && <p className="muted">{t("finalize.empty")}</p>}
      <div className="final-grid">
        {days.map((menu) => (
          <FinalizeCard
            key={menu.id}
            menu={menu}
            serviceStart={settings.data?.service_window_start ?? "12:00:00"}
            serverTime={serverTime}
          />
        ))}
      </div>
    </div>
  );
}

function FinalizeCard({ menu, serviceStart, serverTime }: {
  menu: StaffMenu;
  serviceStart: string;
  serverTime?: string;
}) {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [count, setCount] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  // The final count is locked once the service window opens (FR-27). Both strings are company
  // wall-clock time, so they compare as text; the backend enforces the rule anyway.
  const serviceStarted = Boolean(serverTime && serverTime.slice(0, 19) >= `${menu.date}T${serviceStart}`);
  const canFinalize = (menu.status === "locked" || (menu.status === "finalized" && editing)) && !serviceStarted;

  const proposal = useQuery({
    queryKey: ["finalization", menu.date],
    queryFn: () => menuApi.finalization(menu.date),
    enabled: canFinalize,
  });
  const value = count || String(proposal.data?.proposed ?? "");

  const finalize = useMutation({
    mutationFn: () => menuApi.finalize(menu.date, Number(value)),
    onSuccess: () => {
      setEditing(false);
      setCount("");
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
          {menu.auto_finalized
            ? t("finalize.auto")
            : t("finalize.buffer", { buffer: menu.buffer ?? 0 })}
        </p>
      )}

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
          <Field
            label={t("finalize.finalCount")}
            type="number"
            inputMode="numeric"
            min={proposal.data?.reserved ?? 0}
            value={value}
            onChange={(e) => setCount(e.target.value)}
            required
          />
          <div className="actions">
            <Button type="submit" disabled={finalize.isPending || !value}>{t("finalize.confirm")}</Button>
            {editing && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>{t("common.cancel")}</Button>}
          </div>
        </form>
      )}
      {menu.status === "finalized" && !editing && !serviceStarted && (
        <div className="actions">
          <Button className="btn--sm" variant="ghost" onClick={() => setEditing(true)}>{t("finalize.change")}</Button>
        </div>
      )}
    </Card>
  );
}

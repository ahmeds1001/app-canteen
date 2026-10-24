import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { menuApi, reservationApi } from "@/api/endpoints";
import type { Menu, Reservation } from "@/api/types";
import { Alert, Badge, Button, Card } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { formatDay, isoToday } from "@/utils/dates";
import "./employee.css";

/** FR-11 to FR-13: published days, reserve or cancel in one tap. */
export default function HomePage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");

  const menus = useQuery({ queryKey: ["menus"], queryFn: () => menuApi.list(isoToday()) });
  const mine = useQuery({ queryKey: ["reservations", "upcoming"], queryFn: () => reservationApi.mine(true) });
  const byDate = new Map((mine.data ?? []).filter((r) => r.status !== "cancelled").map((r) => [r.date, r]));

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["reservations"] });
  const reserve = useMutation({ mutationFn: reservationApi.reserve, onSuccess: refresh, onError: (e) => setError(toMessage(e)) });
  const cancel = useMutation({ mutationFn: reservationApi.cancel, onSuccess: refresh, onError: (e) => setError(toMessage(e)) });

  return (
    <div className="container stack">
      <h1>{t("menus.title")}</h1>
      {error && <Alert>{error}</Alert>}
      {menus.data?.length === 0 && <p className="muted">{t("menus.empty")}</p>}
      <div className="days">
        {menus.data?.map((menu) => (
          <DayCard
            key={menu.id}
            menu={menu}
            reservation={byDate.get(menu.date)}
            locale={i18n.language}
            busy={reserve.isPending || cancel.isPending}
            onReserve={() => reserve.mutate(menu.date)}
            onCancel={(id) => cancel.mutate(id)}
          />
        ))}
      </div>
    </div>
  );
}

function DayCard({ menu, reservation, locale, busy, onReserve, onCancel }: {
  menu: Menu;
  reservation?: Reservation;
  locale: string;
  busy: boolean;
  onReserve: () => void;
  onCancel: (id: number) => void;
}) {
  const { t } = useTranslation();
  const open = menu.is_open_for_reservation;

  if (menu.status === "closed" && !reservation) {
    return (
      <Card className="day">
        <div className="day__head">
          <span className="day__date">{formatDay(menu.date, locale)}</span>
          <Badge tone="red">{t("menus.dayClosed")}</Badge>
        </div>
        <p className="day__tba">{t("menus.dayClosedHelp")}</p>
      </Card>
    );
  }

  return (
    <Card className="day">
      <div className="day__head">
        <span className="day__date">{formatDay(menu.date, locale)}</span>
        {reservation ? <Badge tone="green">{t("menus.reserved")}</Badge> : !open && <Badge>{t("menus.closed")}</Badge>}
      </div>
      {menu.items.length === 0 ? (
        <p className="day__tba">{t("menus.toBeAnnounced")}</p>
      ) : (
        <ul className="day__items">
          {menu.items.map((item) => <li key={item.id}>{item.name}</li>)}
        </ul>
      )}
      {menu.is_paid && menu.price && <Badge tone="orange">{t("menus.price", { price: menu.price })}</Badge>}
      <div className="day__actions">
        {open && !reservation && <Button block disabled={busy} onClick={onReserve}>{t("menus.reserve")}</Button>}
        {open && reservation?.status === "reserved" && (
          <Button block variant="danger" disabled={busy} onClick={() => onCancel(reservation.id)}>
            {t("menus.cancel")}
          </Button>
        )}
      </div>
    </Card>
  );
}

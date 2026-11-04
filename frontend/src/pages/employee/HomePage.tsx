import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { menuApi, reservationApi, walletApi } from "@/api/endpoints";
import type { Menu, MenuChoice, MenuItem, Reservation } from "@/api/types";
import { Alert, Badge, Button, Card } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useServerTime } from "@/hooks/useServerTime";
import { formatCompanyDateTime, formatDay, isoToday } from "@/utils/dates";
import "./employee.css";

/** FR-11 to FR-13: published days, pick menu 1 or 2, reserve or cancel in one tap.
 *  Meals are paid from the prepaid balance when reserving (decided 2026-11-03). */
export default function HomePage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  // "Today" follows the server (company time zone, and the dev test clock when it is shifted).
  const { serverTime } = useServerTime();
  const today = serverTime?.slice(0, 10) ?? isoToday();
  const menus = useQuery({ queryKey: ["menus", today], queryFn: () => menuApi.list(today) });
  const mine = useQuery({ queryKey: ["reservations", "upcoming"], queryFn: () => reservationApi.mine(true) });
  const wallet = useQuery({ queryKey: ["wallet", "me"], queryFn: walletApi.me });
  const byDate = new Map((mine.data ?? []).filter((r) => r.status !== "cancelled").map((r) => [r.date, r]));
  const balance = Number(wallet.data?.balance ?? 0);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["reservations"] });
    queryClient.invalidateQueries({ queryKey: ["wallet"] });
  };
  const fail = (e: unknown) => setMessage({ kind: "error", text: toMessage(e) });
  const reserve = useMutation({
    mutationFn: reservationApi.reserve,
    onSuccess: () => { setMessage(null); refresh(); },
    onError: fail,
  });
  const cancel = useMutation({
    mutationFn: reservationApi.cancel,
    onSuccess: (r) => {
      setMessage(r.payment_status === "refunded"
        ? { kind: "success", text: t("menus.refunded", { amount: r.amount_due }) }
        : null);
      refresh();
    },
    onError: fail,
  });

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("menus.title")}</h1>
        {wallet.data && (
          <Link to="/balance" className="balance-chip">
            {t("balance.short", { amount: wallet.data.balance })}
          </Link>
        )}
      </div>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}
      {menus.data?.length === 0 && <p className="muted">{t("menus.empty")}</p>}
      <div className="days">
        {menus.data?.map((menu) => (
          <DayCard
            key={menu.id}
            menu={menu}
            reservation={byDate.get(menu.date)}
            balance={balance}
            locale={i18n.language}
            busy={reserve.isPending || cancel.isPending}
            onReserve={(choice) => reserve.mutate({ date: menu.date, choice })}
            onCancel={(id) => cancel.mutate(id)}
          />
        ))}
      </div>
    </div>
  );
}

function DayCard({ menu, reservation, balance, locale, busy, onReserve, onCancel }: {
  menu: Menu;
  reservation?: Reservation;
  balance: number;
  locale: string;
  busy: boolean;
  onReserve: (choice: MenuChoice) => void;
  onCancel: (id: number) => void;
}) {
  const { t } = useTranslation();
  const open = menu.is_open_for_reservation;
  const twoMenus = menu.choices.length > 1;
  const price = menu.is_paid && menu.price ? Number(menu.price) : 0;
  // Switching menus costs nothing; only a new reservation needs the money.
  const cannotPay = !reservation && price > balance;

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

  // The main dish's photo of the chosen menu (or menu 1), or the first dish that has one (FR-29).
  const shown = menu.items.filter((i) => i.choice === (reservation?.choice ?? 1));
  const photo = shown.find((i) => i.category === "main" && i.photo_url) ?? shown.find((i) => i.photo_url);

  return (
    <Card className="day">
      {photo && <img className="day__photo" src={photo.photo_url!} alt={photo.name} loading="lazy" />}
      <div className="day__head">
        <span className="day__date">{formatDay(menu.date, locale)}</span>
        {reservation ? <Badge tone="green">{t("menus.reserved")}</Badge> : !open && <Badge>{t("menus.closed")}</Badge>}
      </div>
      {price > 0 && <Badge tone="orange">{t("menus.price", { price: menu.price })}</Badge>}

      {menu.items.length === 0 ? (
        <p className="day__tba">{t("menus.toBeAnnounced")}</p>
      ) : (
        menu.choices.map((choice) => {
          const chosen = reservation?.choice === choice;
          return (
            <div key={choice} className={`menu-option ${chosen ? "menu-option--chosen" : ""}`}>
              {twoMenus && (
                <div className="menu-option__head">
                  <strong>{t("menus.menuN", { n: choice })}</strong>
                  {chosen && <Badge tone="green">{t("menus.yourChoice")}</Badge>}
                </div>
              )}
              <Dishes items={menu.items.filter((i) => i.choice === choice)} />
              {open && !reservation && (
                <Button block disabled={busy || cannotPay} onClick={() => onReserve(choice)}>
                  {twoMenus ? t("menus.reserveN", { n: choice }) : t("menus.reserve")}
                </Button>
              )}
              {open && reservation?.status === "reserved" && twoMenus && !chosen && (
                <Button block variant="ghost" disabled={busy} onClick={() => onReserve(choice)}>
                  {t("menus.switchTo")}
                </Button>
              )}
            </div>
          );
        })
      )}

      {/* A placeholder day ("menu to be announced") can still be reserved: it is menu 1. */}
      {menu.items.length === 0 && open && !reservation && (
        <Button block disabled={busy || cannotPay} onClick={() => onReserve(1)}>{t("menus.reserve")}</Button>
      )}
      {open && (
        <p className="day__hint">
          {t("menus.deadline", { date: formatCompanyDateTime(menu.reservation_cutoff, locale) })}
        </p>
      )}
      {open && cannotPay && (
        <p className="day__hint">
          {t("menus.notEnough", { price: menu.price })} <Link to="/balance">{t("balance.how")}</Link>
        </p>
      )}
      {open && reservation?.status === "reserved" && (
        <div className="day__actions">
          <Button block variant="danger" disabled={busy} onClick={() => onCancel(reservation.id)}>
            {price > 0 ? t("menus.cancelRefund", { price: reservation.amount_due }) : t("menus.cancel")}
          </Button>
        </div>
      )}
    </Card>
  );
}

function Dishes({ items }: { items: MenuItem[] }) {
  return (
    <ul className="day__items">
      {items.map((item) => <li key={item.id}>{item.name}</li>)}
    </ul>
  );
}

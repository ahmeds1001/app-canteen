import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { reservationApi } from "@/api/endpoints";
import type { PaymentStatus, ReservationStatus } from "@/api/types";
import { Badge, Card } from "@/components/ui";
import { formatDay } from "@/utils/dates";
import { MealQr } from "./MealQr";
import "./employee.css";

const STATUS_TONE: Record<ReservationStatus, "green" | "orange" | "red" | undefined> = {
  reserved: "green", served: undefined, cancelled: undefined, no_show: "red",
};
const PAY_TONE: Record<PaymentStatus, "green" | "orange" | undefined> = {
  not_required: undefined, unpaid: "orange", paid: "green",
};

/** FR-15 to FR-17: "My reservations" with the QR code shown on the employee's phone. */
export default function ReservationsPage() {
  const { t, i18n } = useTranslation();
  const { data } = useQuery({ queryKey: ["reservations", "upcoming"], queryFn: () => reservationApi.mine(true) });
  const active = (data ?? []).filter((r) => r.status !== "cancelled");

  return (
    <div className="container stack">
      <h1>{t("reservations.title")}</h1>
      {active.length === 0 && <p className="muted">{t("reservations.empty")}</p>}
      {active.map((r) => (
        <Card key={r.id} className="qr-card">
          <h2>{formatDay(r.date, i18n.language)}</h2>
          <div>
            <Badge tone={STATUS_TONE[r.status]}>{t(`reservations.status.${r.status}`)}</Badge>{" "}
            {r.payment_status !== "not_required" && (
              <Badge tone={PAY_TONE[r.payment_status]}>{t(`reservations.payment.${r.payment_status}`)}</Badge>
            )}
          </div>
          {r.menu_items.length > 0 && <p className="muted">{r.menu_items.join(" · ")}</p>}
          {r.qr_payload && (
            <>
              <MealQr payload={r.qr_payload} />
              <p className="muted">{t("reservations.showQr")}</p>
            </>
          )}
        </Card>
      ))}
    </div>
  );
}

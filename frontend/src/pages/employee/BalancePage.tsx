import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { walletApi } from "@/api/endpoints";
import type { BalanceTransaction } from "@/api/types";
import { Alert, Card } from "@/components/ui";
import { useCanteenSettings } from "@/hooks/useCanteenSettings";
import { formatCompanyDateTime, formatShortDate } from "@/utils/dates";
import "./employee.css";

/** The employee's prepaid balance and its history (decided 2026-11-03). */
export default function BalancePage() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["wallet", "me"], queryFn: walletApi.me });
  const { cutoff } = useCanteenSettings();

  return (
    <div className="container stack">
      <h1>{t("balance.title")}</h1>
      <Card className="balance-card">
        <span className="muted">{t("balance.current")}</span>
        <span className="balance-card__amount">{data ? `${data.balance} TND` : "…"}</span>
      </Card>
      <Alert kind="info">{t("balance.howHelp", { cutoff })}</Alert>
      <h2>{t("balance.history")}</h2>
      {data && <Ledger transactions={data.transactions} />}
    </div>
  );
}

/** List of balance movements, newest first. Also used by the cashier screen. */
export function Ledger({ transactions }: { transactions: BalanceTransaction[] }) {
  const { t, i18n } = useTranslation();
  if (transactions.length === 0) return <p className="muted">{t("balance.empty")}</p>;
  return (
    <ul className="ledger">
      {transactions.map((tx) => {
        const incoming = Number(tx.amount) > 0;
        return (
          <li key={tx.id}>
            <span className="ledger__what">
              <strong>
                {t(`balance.kind.${tx.kind}`)}
                {tx.meal_date && ` · ${formatShortDate(tx.meal_date, i18n.language)}`}
              </strong>
              <span className="ledger__meta">
                {formatCompanyDateTime(tx.created_at, i18n.language)}
                {tx.by_name && tx.kind !== "meal" && ` · ${tx.by_name}`}
                {tx.note && ` · ${tx.note}`}
              </span>
            </span>
            <span className="ledger__amount">
              <span className={incoming ? "ledger__amount--in" : "ledger__amount--out"}>
                {incoming ? "+" : ""}{tx.amount} TND
              </span>
              <br />
              <span className="ledger__meta">{t("balance.after", { amount: tx.balance_after })}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

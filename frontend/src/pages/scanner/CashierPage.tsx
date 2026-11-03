import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { walletApi } from "@/api/endpoints";
import type { WalletAccount } from "@/api/types";
import { Alert, Button, Card, Field } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useConfirm } from "@/hooks/useConfirm";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { Ledger } from "@/pages/employee/BalancePage";
import "./scanner.css";

const QUICK_AMOUNTS = ["5", "10", "20", "50"];

/** Prepaid balance (decided 2026-11-03): an employee gives cash at the canteen, the scanner or management
 *  records it here. Management can also correct a mistake, with a reason. Nothing is ever deleted. */
export default function CashierPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [account, setAccount] = useState<WalletAccount | null>(null);
  const found = useQuery({
    queryKey: ["wallet", "search", q],
    queryFn: () => walletApi.search(q.trim()),
    enabled: q.trim().length >= 2,
  });

  return (
    <div className="container stack">
      <h1>{t("cashier.title")}</h1>
      <p className="muted">{t("cashier.help")}</p>
      {!account ? (
        <Card className="stack">
          <Field label={t("cashier.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          {found.data?.length === 0 && <p className="muted">{t("cashier.noMatch")}</p>}
          {found.data?.map((a) => (
            <button key={a.id} type="button" className="cashier__match" onClick={() => setAccount(a)}>
              <span>
                <strong>{a.full_name}</strong>
                <span className="muted"> · {a.employee_number ?? "—"}{a.department && ` · ${a.department}`}</span>
              </span>
              <span className="cashier__balance">{a.balance} TND</span>
            </button>
          ))}
        </Card>
      ) : (
        <AccountPanel account={account} onBack={() => setAccount(null)} />
      )}
    </div>
  );
}

function AccountPanel({ account, onBack }: { account: WalletAccount; onBack: () => void }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const history = useQuery({ queryKey: ["wallet", "account", account.id], queryFn: () => walletApi.history(account.id) });
  const current = history.data?.account ?? account;
  const canCorrect = user?.role === "management" || user?.role === "admin";

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["wallet"] });
  const topUp = useMutation({
    mutationFn: () => walletApi.topUp(account.id, Number(amount).toFixed(3)),
    onSuccess: (res) => {
      setMessage({ kind: "success", text: t("cashier.done", { amount: Number(amount).toFixed(3), balance: res.account.balance }) });
      setAmount("");
      refresh();
    },
    onError: (e) => setMessage({ kind: "error", text: toMessage(e) }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    // Cash changes hands: say the amount and the name out loud before recording it.
    confirm.ask(t("cashier.confirm", { amount: Number(amount).toFixed(3), name: account.full_name }), () => topUp.mutate());
  };

  return (
    <div className="stack">
      <div>
        <Button className="btn--sm" variant="ghost" onClick={onBack}>‹ {t("cashier.back")}</Button>
      </div>
      <Card className="balance-card">
        <strong>{current.full_name}</strong>
        <span className="muted">{current.employee_number ?? "—"}{current.department && ` · ${current.department}`}</span>
        <span className="balance-card__amount">{current.balance} TND</span>
      </Card>
      {message && <Alert kind={message.kind}>{message.text}</Alert>}
      <Card>
        <form className="stack" onSubmit={submit}>
          <h2>{t("cashier.topUp")}</h2>
          <div className="actions">
            {QUICK_AMOUNTS.map((a) => (
              <Button key={a} type="button" className="btn--sm" variant={amount === a ? "primary" : "ghost"} onClick={() => setAmount(a)}>
                {a} TND
              </Button>
            ))}
          </div>
          <Field
            label={t("cashier.amount")}
            type="number"
            inputMode="decimal"
            min="0.001"
            max="1000"
            step="0.001"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
          <Button type="submit" block disabled={topUp.isPending || !(Number(amount) > 0)}>
            {t("cashier.record", { amount: Number(amount) > 0 ? Number(amount).toFixed(3) : "…" })}
          </Button>
        </form>
      </Card>
      {canCorrect && <CorrectionForm account={account} onDone={(text) => { setMessage({ kind: "success", text }); refresh(); }} />}
      <h2>{t("balance.history")}</h2>
      {history.data && <Ledger transactions={history.data.transactions} />}
      {confirm.dialog}
    </div>
  );
}

/** Management only: fix a mistake (wrong amount, wrong person). Negative takes money off. */
function CorrectionForm({ account, onDone }: { account: WalletAccount; onDone: (text: string) => void }) {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const correct = useMutation({
    mutationFn: () => walletApi.correct(account.id, Number(amount).toFixed(3), reason),
    onSuccess: (res) => {
      onDone(t("cashier.corrected", { balance: res.account.balance }));
      setOpen(false);
      setAmount("");
      setReason("");
      setError("");
    },
    onError: (e) => setError(toMessage(e)),
  });

  if (!open) {
    return (
      <div>
        <Button className="btn--sm" variant="ghost" onClick={() => setOpen(true)}>{t("cashier.correct")}</Button>
      </div>
    );
  }
  return (
    <Card>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); correct.mutate(); }}>
        <h2>{t("cashier.correct")}</h2>
        <p className="muted">{t("cashier.correctHelp")}</p>
        {error && <Alert>{error}</Alert>}
        <Field label={t("cashier.correctAmount")} type="number" inputMode="decimal" step="0.001" value={amount}
          onChange={(e) => setAmount(e.target.value)} required />
        <Field label={t("cashier.reason")} value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} required />
        <div className="actions">
          <Button type="submit" disabled={correct.isPending || !Number(amount) || !reason.trim()}>{t("common.save")}</Button>
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
        </div>
      </form>
    </Card>
  );
}

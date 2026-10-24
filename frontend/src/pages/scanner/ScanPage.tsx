import { Html5Qrcode } from "html5-qrcode";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { scanApi } from "@/api/endpoints";
import type { ScanResult } from "@/api/types";
import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import "./scanner.css";

/** FR-18 to FR-20, FR-34: dedicated canteen phone. Big green / red result, payment badge.
 *  TODO (backlog): offline queue — store failed-network scans with their timestamp and resend. */
export default function ScanPage() {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const reader = useRef<Html5Qrcode | null>(null);
  const lastPayload = useRef("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ScanResult[]>([]);

  useEffect(() => () => void reader.current?.stop().catch(() => undefined), []);

  async function handle(payload: string) {
    if (payload === lastPayload.current) return; // camera reads the same code many times per second
    lastPayload.current = payload;
    setError("");
    try {
      setResult(await scanApi.scan(payload));
    } catch (err) {
      setResult(null);
      setError(toMessage(err));
    }
    setTimeout(() => (lastPayload.current = ""), 3000);
  }

  async function start() {
    reader.current = new Html5Qrcode("qr-reader");
    await reader.current.start({ facingMode: "environment" }, { fps: 10, qrbox: 240 }, handle, () => undefined);
    setRunning(true);
  }

  async function stop() {
    await reader.current?.stop();
    setRunning(false);
  }

  async function search(q: string) {
    setQuery(q);
    setMatches(q.trim().length >= 2 ? await scanApi.search(q) : []);
  }

  async function act(fn: () => Promise<ScanResult>) {
    setError("");
    try {
      setResult(await fn());
      if (query) setMatches(await scanApi.search(query));
    } catch (err) {
      setError(toMessage(err));
    }
  }

  return (
    <div className="container stack">
      <h1>{t("scan.title")}</h1>
      <div id="qr-reader" className="scanner__camera" />
      <Button block variant={running ? "ghost" : "primary"} onClick={running ? stop : start}>
        {running ? t("scan.stop") : t("scan.start")}
      </Button>

      {error && <div className="scanner__result scanner__result--error" role="alert">{error}</div>}
      {result && (
        <div className="scanner__result scanner__result--ok" role="status">
          <strong>{t("scan.ok")}</strong>
          <span className="scanner__name">{result.full_name}</span>
          <span>{result.employee_number}</span>
          {result.payment_status === "unpaid" && (
            <>
              <Badge tone="orange">{t("scan.toPay", { amount: result.amount_due })}</Badge>
              <Button variant="accent" onClick={() => act(() => scanApi.markPaid(result.id))}>{t("scan.markPaid")}</Button>
            </>
          )}
          {result.payment_status === "paid" && <Badge tone="green">{t("scan.paid")}</Badge>}
        </div>
      )}

      <Card className="stack">
        <Field label={t("scan.manualSearch")} value={query} onChange={(e) => search(e.target.value)} />
        {matches.map((m) => (
          <div key={m.id} className="scanner__match">
            <span>{m.full_name} · {m.employee_number}</span>
            {m.status === "reserved" ? (
              <Button variant="ghost" onClick={() => act(() => scanApi.manual(m.id))}>{t("scan.checkIn")}</Button>
            ) : (
              <Badge>{t(`reservations.status.${m.status}`)}</Badge>
            )}
          </div>
        ))}
      </Card>
      {!result && !error && <Alert kind="info">{t("reservations.showQr")}</Alert>}
    </div>
  );
}

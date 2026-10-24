import { Html5Qrcode } from "html5-qrcode";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { scanApi } from "@/api/endpoints";
import type { ScanResult } from "@/api/types";
import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import "./scanner.css";

/** A code that stays in front of the camera is read many times per second. It is sent once, and again
 *  only after it has been out of view for this long (otherwise "validated" flips to "already served"). */
const SAME_CODE_GAP_MS = 2500;

function vibrate(pattern: number | number[]) {
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* not supported */
  }
}

/** FR-18 to FR-20, FR-34: dedicated canteen phone. Big green / red result, payment badge.
 *  TODO (backlog): offline queue — store failed-network scans with their timestamp and resend. */
export default function ScanPage() {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const reader = useRef<Html5Qrcode | null>(null);
  const lastPayload = useRef("");
  const lastSeenAt = useRef(0);
  const busy = useRef(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ScanResult[]>([]);

  useEffect(() => () => void reader.current?.stop().catch(() => undefined), []);

  async function handle(payload: string) {
    const now = Date.now();
    const sameCodeStillInView = payload === lastPayload.current && now - lastSeenAt.current < SAME_CODE_GAP_MS;
    lastSeenAt.current = now;
    if (sameCodeStillInView || busy.current) return;
    lastPayload.current = payload;
    busy.current = true;
    try {
      const scanned = await scanApi.scan(payload);
      setError("");
      setResult(scanned);
      vibrate(150);
    } catch (err) {
      setResult(null);
      setError(toMessage(err));
      vibrate([80, 60, 80, 60, 80]);
    } finally {
      busy.current = false;
      lastSeenAt.current = Date.now();
    }
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

  // The result sits above the camera and the camera border turns green / red, so staff see the
  // outcome while still aiming (below the camera it was off-screen on a phone).
  const outcome = error ? "error" : result ? "ok" : "";

  return (
    <div className="container stack">
      <h1>{t("scan.title")}</h1>
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
      {!result && !error && <Alert kind="info">{t("scan.hint")}</Alert>}

      <div className={`scanner__frame ${outcome ? `scanner__frame--${outcome}` : ""}`}>
        <div id="qr-reader" className="scanner__camera" />
      </div>
      <Button block variant={running ? "ghost" : "primary"} onClick={running ? stop : start}>
        {running ? t("scan.stop") : t("scan.start")}
      </Button>

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
    </div>
  );
}

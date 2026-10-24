import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authApi } from "@/api/endpoints";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Alert, Button, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";

const RESEND_DELAY = 60;

/** FR-02: 6-digit code, valid 10 min, resend after 60 s. */
export default function VerifyOtpPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toMessage = useErrorMessage();
  const [params] = useSearchParams();
  const email = params.get("email") ?? "";
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [wait, setWait] = useState(RESEND_DELAY);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return;
    const id = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(id);
  }, [wait]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authApi.verifyOtp(email, code);
      navigate("/pending");
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError("");
    try {
      await authApi.resendOtp(email);
      setInfo(t("auth.resent"));
      setWait(RESEND_DELAY);
    } catch (err) {
      setError(toMessage(err));
    }
  }

  return (
    <AuthLayout title={t("auth.otpTitle")}>
      <form className="stack" onSubmit={submit}>
        <p className="muted">{t("auth.otpHelp", { email })}</p>
        {error && <Alert>{error}</Alert>}
        {info && <Alert kind="success">{info}</Alert>}
        <Field label={t("auth.otpCode")} className="otp" inputMode="numeric" autoComplete="one-time-code"
          maxLength={6} pattern="\d{6}" required value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
        <Button type="submit" block disabled={busy || code.length !== 6}>{t("auth.verify")}</Button>
        <Button type="button" variant="ghost" block disabled={wait > 0} onClick={resend}>
          {t("auth.resend")}{wait > 0 ? ` (${wait}s)` : ""}
        </Button>
      </form>
    </AuthLayout>
  );
}

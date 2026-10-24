import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { authApi } from "@/api/endpoints";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Alert, Button, Field } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useErrorMessage } from "@/hooks/useErrorMessage";

export default function LoginPage() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const toMessage = useErrorMessage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await authApi.login(email, password);
      signIn(data);
      navigate(data.user.role === "scanner" ? "/scan" : "/");
    } catch (err) {
      // An unverified account goes back to the code screen (FR-02).
      if (err instanceof ApiError && err.code === "email_not_verified") {
        navigate(`/verify?email=${encodeURIComponent(email)}`);
        return;
      }
      if (err instanceof ApiError && err.code === "pending_hr") {
        navigate("/pending");
        return;
      }
      setError(toMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title={t("auth.login")}>
      <form className="stack" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}
        <Field label={t("auth.email")} type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
        <Field label={t("auth.password")} type="password" autoComplete="current-password" required
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" block disabled={busy}>{t("auth.login")}</Button>
        <p><Link to="/forgot-password">{t("auth.forgot")}</Link></p>
        <p className="muted">
          {t("auth.noAccount")} <Link to="/register">{t("auth.register")}</Link>
        </p>
      </form>
    </AuthLayout>
  );
}

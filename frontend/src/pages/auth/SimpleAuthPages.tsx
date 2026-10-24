import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authApi } from "@/api/endpoints";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Alert, Button, Field } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useErrorMessage } from "@/hooks/useErrorMessage";

export function PendingPage() {
  const { t } = useTranslation();
  return (
    <AuthLayout title={t("auth.pendingTitle")}>
      <p>{t("auth.pendingHelp")}</p>
      <Link to="/login">{t("auth.login")}</Link>
    </AuthLayout>
  );
}

/** FR-39: self-service reset link. */
export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    await authApi.forgotPassword(email).catch(() => undefined);
    setSent(true); // same answer whether the email exists or not
  }

  return (
    <AuthLayout title={t("auth.forgotTitle")}>
      <form className="stack" onSubmit={submit}>
        <p className="muted">{t("auth.forgotHelp")}</p>
        {sent && <Alert kind="success">{t("auth.linkSent")}</Alert>}
        <Field label={t("auth.email")} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button type="submit" block>{t("auth.sendLink")}</Button>
        <Link to="/login">{t("auth.login")}</Link>
      </form>
    </AuthLayout>
  );
}

export function ResetPasswordPage() {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await authApi.resetPassword(params.get("token") ?? "", password);
      setDone(true);
    } catch (err) {
      setError(toMessage(err));
    }
  }

  return (
    <AuthLayout title={t("auth.resetTitle")}>
      <form className="stack" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}
        {done ? (
          <>
            <Alert kind="success">{t("auth.resetDone")}</Alert>
            <Link to="/login">{t("auth.login")}</Link>
          </>
        ) : (
          <>
            <Field label={t("auth.newPassword")} type="password" autoComplete="new-password" required
              value={password} onChange={(e) => setPassword(e.target.value)} />
            <Button type="submit" block>{t("auth.save")}</Button>
          </>
        )}
      </form>
    </AuthLayout>
  );
}

/** FR-40: forced change after an HR reset (temporary password). */
export function MustChangePasswordPage() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const toMessage = useErrorMessage();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      signIn(await authApi.changePassword(password));
      navigate("/");
    } catch (err) {
      setError(toMessage(err));
    }
  }

  return (
    <AuthLayout title={t("auth.mustChangeTitle")}>
      <form className="stack" onSubmit={submit}>
        <p className="muted">{t("auth.mustChangeHelp")}</p>
        {error && <Alert>{error}</Alert>}
        <Field label={t("auth.newPassword")} type="password" autoComplete="new-password" required
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" block>{t("auth.save")}</Button>
      </form>
    </AuthLayout>
  );
}

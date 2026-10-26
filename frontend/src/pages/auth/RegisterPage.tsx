import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { authApi } from "@/api/endpoints";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Alert, Button, Field, PasswordRules } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";

// No employee number here: HR enters it when approving the account.
const EMPTY = { first_name: "", last_name: "", work_email: "", department: "", password: "" };

export default function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toMessage = useErrorMessage();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const bind = (name: keyof typeof EMPTY) => ({
    value: form[name],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [name]: e.target.value }),
    error: errors[name]?.join(" "),
  });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setErrors({});
    try {
      await authApi.register(form);
      navigate(`/verify?email=${encodeURIComponent(form.work_email)}`);
    } catch (err) {
      // Field errors go under their field; anything else (password rules checked across fields,
      // "too many attempts"…) goes in the banner. Before, those were silently dropped.
      const fields = err instanceof ApiError && err.fields && err.code === "http_400" ? err.fields : {};
      const own = Object.fromEntries(Object.entries(fields).filter(([name]) => name in EMPTY));
      const other = Object.entries(fields).filter(([name]) => !(name in EMPTY)).flatMap(([, msgs]) => msgs);
      setErrors(own);
      if (other.length) setError(other.join(" "));
      else if (!Object.keys(own).length) setError(toMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title={t("auth.register")}>
      <form className="stack" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}
        <Field label={t("auth.firstName")} required autoComplete="given-name" {...bind("first_name")} />
        <Field label={t("auth.lastName")} required autoComplete="family-name" {...bind("last_name")} />
        <Field label={t("auth.email")} type="email" required autoComplete="email" {...bind("work_email")} />
        <Field label={t("auth.department")} {...bind("department")} />
        <Field label={t("auth.password")} type="password" required autoComplete="new-password"
          {...bind("password")} />
        <PasswordRules password={form.password} />
        <Button type="submit" block disabled={busy}>{t("auth.register")}</Button>
        <p className="muted">
          {t("auth.haveAccount")} <Link to="/login">{t("auth.login")}</Link>
        </p>
      </form>
    </AuthLayout>
  );
}

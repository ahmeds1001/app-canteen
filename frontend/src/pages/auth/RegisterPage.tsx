import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { authApi } from "@/api/endpoints";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Alert, Button, Field } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";

const EMPTY = { first_name: "", last_name: "", work_email: "", employee_number: "", department: "", password: "" };

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
      if (err instanceof ApiError && err.fields) setErrors(err.fields);
      else setError(toMessage(err));
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
        <Field label={t("auth.employeeNumber")} required {...bind("employee_number")} />
        <Field label={t("auth.department")} {...bind("department")} />
        <Field label={t("auth.password")} type="password" required autoComplete="new-password"
          {...bind("password")} />
        <Button type="submit" block disabled={busy}>{t("auth.register")}</Button>
        <p className="muted">
          {t("auth.haveAccount")} <Link to="/login">{t("auth.login")}</Link>
        </p>
      </form>
    </AuthLayout>
  );
}

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Card, Logo } from "@/components/ui";
import "./layout.css";

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <main className="auth">
      <Card className="auth__card stack">
        <div className="auth__brand">
          <Logo size={96} />
          <span className="auth__app">{t("app.name")}</span>
        </div>
        <h1>{title}</h1>
        {children}
      </Card>
    </main>
  );
}

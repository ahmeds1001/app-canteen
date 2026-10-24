import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Role } from "@/api/types";
import { Button, Logo } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { LANGUAGES, applyLanguage } from "@/i18n";
import "./layout.css";

/** Navigation per role (spec §2). Every staff member is also an employee who eats. */
const NAV: Record<Role, { to: string; key: string }[]> = {
  employee: [
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
  ],
  chef: [
    { to: "/", key: "nav.home" },
    { to: "/chef/planner", key: "nav.planner" },
    { to: "/chef/dishes", key: "nav.dishes" },
  ],
  management: [
    { to: "/", key: "nav.home" },
    { to: "/management/finalize", key: "nav.finalize" },
    { to: "/management/reports", key: "nav.reports" },
  ],
  hr: [
    { to: "/", key: "nav.home" },
    { to: "/hr/accounts", key: "nav.accounts" },
    { to: "/hr/reports", key: "nav.reports" },
  ],
  scanner: [{ to: "/scan", key: "nav.scan" }],
  admin: [
    { to: "/", key: "nav.home" },
    { to: "/hr/accounts", key: "nav.accounts" },
    { to: "/management/reports", key: "nav.reports" },
  ],
};

export function AppLayout() {
  const { t, i18n } = useTranslation();
  const { user, signOut } = useAuth();
  const links = user ? NAV[user.role] : [];

  return (
    <div className="shell">
      <header className="shell__bar">
        <Logo size={40} />
        <span className="shell__title">{t("app.name")}</span>
        <nav className="shell__nav" aria-label="Main">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end>
              {t(l.key)}
            </NavLink>
          ))}
        </nav>
        <div className="shell__tools">
          <select
            aria-label={t("app.language")}
            value={i18n.language}
            onChange={(e) => applyLanguage(e.target.value)}
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.code.toUpperCase()}
              </option>
            ))}
          </select>
          <Button variant="ghost" onClick={signOut}>
            {t("app.logout")}
          </Button>
        </div>
      </header>
      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}

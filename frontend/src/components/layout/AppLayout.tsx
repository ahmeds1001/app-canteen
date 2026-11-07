import { useLayoutEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Role } from "@/api/types";
import { Button, Logo } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useServerTime } from "@/hooks/useServerTime";
import { LANGUAGES, applyLanguage } from "@/i18n";
import { formatCompanyDateTime } from "@/utils/dates";
import { NotificationBell } from "./NotificationBell";
import "./layout.css";

/** Navigation per role (spec §2). Every staff member is also an employee who eats: "Menus" to reserve and
 *  "Mes réservations" for the QR code are in every menu; "Mon solde" opens from the balance button on "Menus". */
const NAV: Record<Role, { to: string; key: string }[]> = {
  employee: [
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
    { to: "/balance", key: "nav.balance" },
  ],
  chef: [
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
    { to: "/chef/planner", key: "nav.planner" },
    { to: "/chef/dishes", key: "nav.dishes" },
  ],
  management: [
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
    { to: "/management/finalize", key: "nav.finalize" },
    { to: "/day-list", key: "nav.dayList" },
    { to: "/cashier", key: "nav.cashier" },
    { to: "/cash", key: "nav.cash" },
    { to: "/management/reports", key: "nav.reports" },
  ],
  hr: [
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
    { to: "/hr/accounts", key: "nav.accounts" },
    { to: "/hr/reports", key: "nav.reports" },
  ],
  // The canteen phone scans (no money since 2026-11-05, FR-47); the staff using it eat at the canteen too.
  scanner: [
    { to: "/scan", key: "nav.scan" },
    { to: "/day-list", key: "nav.dayList" },
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
  ],
  // FR-47: the cashier records the cash employees hand in, and hands it over to management.
  cashier: [
    { to: "/cashier", key: "nav.cashier" },
    { to: "/cash", key: "nav.cash" },
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
  ],
  admin: [
    { to: "/", key: "nav.home" },
    { to: "/reservations", key: "nav.reservations" },
    { to: "/chef/planner", key: "nav.planner" },
    { to: "/management/finalize", key: "nav.finalize" },
    { to: "/day-list", key: "nav.dayList" },
    { to: "/cashier", key: "nav.cashier" },
    { to: "/cash", key: "nav.cash" },
    { to: "/hr/accounts", key: "nav.accounts" },
    { to: "/management/reports", key: "nav.reports" },
    { to: "/admin/settings", key: "nav.settings" },
  ],
};

export function AppLayout() {
  const { t, i18n } = useTranslation();
  const { user, signOut } = useAuth();
  const { serverTime, shifted } = useServerTime();
  const links = user ? NAV[user.role] : [];
  // A role with a single screen would get no menu bar (none today; kept for future roles).
  const showNav = links.length > 1;
  const { ref: barRef, layout } = useBarLayout(`${user?.role}|${i18n.language}`);

  return (
    <div className="shell">
      <header ref={barRef} className={`shell__bar ${layout ? `shell__bar--${layout}` : ""}`}>
        <Logo size={40} />
        <span className="shell__title">{t("app.name")}</span>
        {showNav && (
          <nav className="shell__nav" aria-label={t("app.mainNav")}>
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end>
                {t(l.key)}
              </NavLink>
            ))}
          </nav>
        )}
        <div className="shell__tools">
          {user && <NotificationBell />}
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
      {shifted && serverTime && (
        <div className="shell__devclock" role="status">
          {t("app.devClock", { time: formatCompanyDateTime(serverTime, i18n.language) })}
        </div>
      )}
      <main className={`shell__main ${showNav ? "" : "shell__main--no-nav"}`}>
        <Outlet />
      </main>
    </div>
  );
}

type BarLayout = "" | "compact" | "stacked";

/** Chooses how the header fits its width: one line with the title, one line without it, or the menu on its own
 *  row. Measured from the widths of the items themselves (they do not change between layouts), so switching
 *  layout never makes it switch back. Phones (720 px and less) use the bottom tab bar instead. */
function useBarLayout(key: string) {
  const ref = useRef<HTMLElement>(null);
  const titleWidth = useRef(0);
  const [layout, setLayout] = useState<BarLayout>("");

  useLayoutEffect(() => {
    const bar = ref.current;
    if (!bar) return;
    const width = (selector: string) => bar.querySelector<HTMLElement>(selector)?.getBoundingClientRect().width ?? 0;
    const measure = () => {
      if (window.innerWidth <= 720) return setLayout("");
      const css = getComputedStyle(bar);
      const gap = parseFloat(css.columnGap) || 0;
      const room = bar.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight);
      const nav = bar.querySelector<HTMLElement>(".shell__nav");
      const links = nav ? Array.from(nav.children) : [];
      const navGap = nav ? parseFloat(getComputedStyle(nav).columnGap) || 0 : 0;
      const navWidth = links.reduce((sum, a) => sum + a.getBoundingClientRect().width, 0)
        + navGap * Math.max(links.length - 1, 0);
      titleWidth.current = width(".shell__title") || titleWidth.current; // 0 while hidden: keep the last width
      const oneLine = width(".logo") + navWidth + width(".shell__tools") + gap * 2 + 2; // +2: rounding
      setLayout(oneLine + titleWidth.current + gap <= room ? "" : oneLine <= room ? "compact" : "stacked");
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(bar);
    document.fonts?.ready.then(measure); // text widths change once the web fonts arrive
    return () => observer.disconnect();
  }, [key]);

  return { ref, layout };
}

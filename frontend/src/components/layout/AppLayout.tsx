import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Role } from "@/api/types";
import { Logo } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { useServerTime } from "@/hooks/useServerTime";
import { LANGUAGES, applyLanguage } from "@/i18n";
import { formatCompanyDateTime } from "@/utils/dates";
import { Icon, type IconName } from "./icons";
import { NotificationBell } from "./NotificationBell";
import "./layout.css";

/** Every screen of the menus: one name per screen, the same on phones and on wider screens. */
const SCREENS = {
  home: { to: "/", key: "nav.home", icon: "menus" },
  reservations: { to: "/reservations", key: "nav.reservations", icon: "reservations" },
  balance: { to: "/balance", key: "nav.balance", icon: "balance" },
  planner: { to: "/chef/planner", key: "nav.planner", icon: "planner" },
  dishes: { to: "/chef/dishes", key: "nav.dishes", icon: "dishes" },
  finalize: { to: "/management/finalize", key: "nav.finalize", icon: "finalize" },
  dayList: { to: "/day-list", key: "nav.dayList", icon: "dayList" },
  cashier: { to: "/cashier", key: "nav.cashier", icon: "cashier" },
  cash: { to: "/cash", key: "nav.cash", icon: "cash" },
  hrReports: { to: "/hr/reports", key: "nav.reports", icon: "reports" },
  reports: { to: "/management/reports", key: "nav.reports", icon: "reports" },
  accounts: { to: "/hr/accounts", key: "nav.accounts", icon: "accounts" },
  scan: { to: "/scan", key: "nav.scan", icon: "scan" },
  settings: { to: "/settings", key: "nav.settings", icon: "settings" },
} satisfies Record<string, { to: string; key: string; icon: IconName }>;
type Screen = keyof typeof SCREENS;

/** Navigation per role (spec §2): at most 4 tabs; the other screens go in "Plus", by group. Every staff member is
 *  also an employee who eats: "Menus" and "Réservations" (QR code) are in every menu, "Mon solde" in the
 *  account menu (and on the "Menus" screen). */
const NAV: Record<Role, { main: Screen[]; more?: { key: string; items: Screen[] }[] }> = {
  employee: { main: ["home", "reservations", "balance"] },
  chef: { main: ["home", "reservations", "planner", "dishes"] },
  hr: { main: ["home", "reservations", "accounts", "hrReports"] },
  // The canteen phone scans (no money since 2026-11-05, FR-47); the staff using it eat at the canteen too.
  scanner: { main: ["scan", "dayList", "home", "reservations"] },
  // FR-47: the cashier records the cash employees hand in, and hands it over to management.
  cashier: { main: ["cashier", "cash", "home", "reservations"] },
  management: {
    main: ["home", "reservations", "finalize"],
    more: [
      { key: "navGroup.kitchen", items: ["dayList"] },
      { key: "navGroup.money", items: ["cashier", "cash"] },
      { key: "navGroup.followUp", items: ["reports"] },
    ],
  },
  admin: {
    main: ["home", "reservations", "accounts"],
    more: [
      { key: "navGroup.kitchen", items: ["planner", "finalize", "dayList"] },
      { key: "navGroup.money", items: ["cashier", "cash"] },
      { key: "navGroup.followUp", items: ["reports"] },
      { key: "navGroup.admin", items: ["settings"] },
    ],
  },
};

export function AppLayout() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const { serverTime, shifted } = useServerTime();
  const nav = user ? NAV[user.role] : { main: [] };
  // A role with a single screen would get no menu bar (none today; kept for future roles).
  const showNav = nav.main.length + (nav.more ? 1 : 0) > 1;
  const { ref: barRef, layout } = useBarLayout(`${user?.role}|${i18n.language}`);

  return (
    <div className="shell">
      <header ref={barRef} className={`shell__bar ${layout ? `shell__bar--${layout}` : ""}`}>
        <Logo size={40} />
        <span className="shell__title">{t("app.name")}</span>
        {showNav && (
          <nav className="shell__nav" aria-label={t("app.mainNav")}>
            {nav.main.map((id) => {
              const s = SCREENS[id];
              return (
                <NavLink key={id} to={s.to} end={s.to === "/"} className="navtab">
                  <Icon name={s.icon} />
                  <span className="navtab__label">{t(s.key)}</span>
                </NavLink>
              );
            })}
            {nav.more && <MoreMenu groups={nav.more} />}
          </nav>
        )}
        <div className="shell__tools">
          {user && <NotificationBell />}
          {user && <AccountMenu />}
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

/** "Plus": the screens that do not fit in the tab bar, by group. A sheet from the bottom on phones, a panel under
 *  the button on wider screens. The tab is highlighted when the current screen is one of them. */
function MoreMenu({ groups }: { groups: { key: string; items: Screen[] }[] }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { open, setOpen, rootRef } = usePopup();
  const panelId = useId();
  const current = groups.some((g) => g.items.some((id) => isUnder(pathname, SCREENS[id].to)));

  return (
    <div ref={rootRef} className="more">
      <button
        type="button"
        className={`navtab ${current ? "active" : ""}`}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
      >
        <Icon name="more" />
        <span className="navtab__label">{t("nav.more")}</span>
      </button>
      {open && (
        <>
          <div className="popup-backdrop" onClick={() => setOpen(false)} />
          <div id={panelId} className="popup more__panel">
            {groups.map((g) => (
              <section key={g.key} className="more__group">
                <h2 className="more__title">{t(g.key)}</h2>
                {g.items.map((id) => {
                  const s = SCREENS[id];
                  return (
                    <NavLink key={id} to={s.to} className="popup__item">
                      <Icon name={s.icon} />
                      <span>{t(s.key)}</span>
                    </NavLink>
                  );
                })}
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/** The person's initials; opens their name and role, "Mon solde", the language and "Se déconnecter". */
function AccountMenu() {
  const { t, i18n } = useTranslation();
  const { user, signOut } = useAuth();
  const { open, setOpen, rootRef } = usePopup();
  const panelId = useId();
  if (!user) return null;
  const initials = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase() || "?";

  return (
    <div ref={rootRef} className="usermenu">
      <button
        type="button"
        className="usermenu__button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={t("account.open", { name: user.full_name })}
        onClick={() => setOpen(!open)}
      >
        {initials}
      </button>
      {open && (
        <>
          <div className="popup-backdrop popup-backdrop--clear" onClick={() => setOpen(false)} />
          <div id={panelId} className="popup usermenu__panel">
            <div className="usermenu__who">
              <strong>{user.full_name}</strong>
              <span className="muted">{t(`accounts.roles.${user.role}`)}</span>
              <span className="muted usermenu__email">{user.work_email}</span>
            </div>
            <NavLink to="/balance" end className="popup__item">
              <Icon name="balance" />
              <span>{t("nav.balance")}</span>
            </NavLink>
            <div className="usermenu__lang" role="group" aria-label={t("app.language")}>
              <span className="muted">{t("app.language")}</span>
              <div className="usermenu__langs">
                {LANGUAGES.map((l) => (
                  <button
                    key={l.code}
                    type="button"
                    aria-pressed={i18n.language === l.code}
                    onClick={() => applyLanguage(l.code)}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
            <button type="button" className="popup__item usermenu__logout" onClick={signOut}>
              <Icon name="logout" />
              <span>{t("app.logout")}</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/** Open/closed state of a menu: closes on Escape, on a click outside and when the screen changes. */
function usePopup() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      rootRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    };
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    // Keyboard: tabbing out of the menu closes it.
    const onFocusOut = (e: FocusEvent) => {
      const next = e.relatedTarget as Node | null;
      if (next && !rootRef.current?.contains(next)) setOpen(false);
    };
    const root = rootRef.current;
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    root?.addEventListener("focusout", onFocusOut);
    // Keyboard users land on the first entry of the menu.
    rootRef.current?.querySelector<HTMLElement>(".popup a, .popup button")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
      root?.removeEventListener("focusout", onFocusOut);
    };
  }, [open]);

  return { open, setOpen, rootRef };
}

/** The screen at `to`, or a page inside it (e.g. /chef/planner/…). */
function isUnder(pathname: string, to: string) {
  return pathname === to || pathname.startsWith(`${to}/`);
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

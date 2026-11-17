/** Line icons of the app menus (24×24, drawn with the text colour). Inline SVG: no icon package to install. */
export type IconName =
  | "menus" | "reservations" | "balance" | "planner" | "dishes" | "finalize" | "dayList"
  | "cashier" | "cash" | "reports" | "accounts" | "scan" | "settings" | "more" | "logout";

const PATHS: Record<IconName, string[]> = {
  // fork and knife
  menus: ["M6 3v8a2 2 0 0 0 2 2v8", "M10 3v8a2 2 0 0 1-2 2", "M8 3v6", "M17 21V3c-2 1.5-3 4-3 7v3h3"],
  // ticket with a QR corner
  reservations: ["M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4Z", "M9 9h2v2H9z", "M13 13h2v2h-2z"],
  // wallet
  balance: ["M4 7a2 2 0 0 1 2-2h11v4", "M4 7v10a2 2 0 0 0 2 2h13V9H6a2 2 0 0 1-2-2Z", "M15.5 14h.01"],
  // calendar
  planner: ["M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z", "M4 10h16", "M8 3v4", "M16 3v4", "M8 14h2", "M14 14h2"],
  // bowl with steam
  dishes: ["M3 12h18a9 9 0 0 1-18 0Z", "M9 8c0-1.5 1-1.5 1-3", "M14 8c0-1.5 1-1.5 1-3"],
  // clipboard with a tick
  finalize: ["M9 4h6v3H9z", "M15 5h2a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2", "m9 14 2 2 4-4"],
  // list
  dayList: ["M9 6h11", "M9 12h11", "M9 18h11", "M4.5 6h.01", "M4.5 12h.01", "M4.5 18h.01"],
  // banknote
  cashier: ["M3 7h18v10H3z", "M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z", "M6 10v.01", "M18 14v.01"],
  // receipt
  cash: ["M6 3h12v18l-3-2-3 2-3-2-3 2Z", "M9 8h6", "M9 12h6", "M9 16h3"],
  // bar chart
  reports: ["M4 20h16", "M7 16v-5", "M12 16V6", "M17 16v-8"],
  // two people
  accounts: ["M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z", "M2.5 20a6.5 6.5 0 0 1 13 0", "M16 4.5a3.5 3.5 0 0 1 0 6.5", "M18.5 14a6.5 6.5 0 0 1 3 6"],
  // scan frame
  scan: ["M4 8V5a1 1 0 0 1 1-1h3", "M16 4h3a1 1 0 0 1 1 1v3", "M20 16v3a1 1 0 0 1-1 1h-3", "M8 20H5a1 1 0 0 1-1-1v-3", "M4 12h16"],
  // gear
  settings: [
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z",
  ],
  // three dots
  more: [
    "M6.5 12a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z",
    "M13.5 12a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z",
    "M20.5 12a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z",
  ],
  // door with an arrow
  logout: ["M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4", "m16 17 5-5-5-5", "M21 12H9"],
};

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="icon"
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

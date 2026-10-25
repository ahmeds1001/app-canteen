import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { notificationApi } from "@/api/endpoints";

/** Bell in the app bar with the unread count (spec §8). Polls every minute. */
export function NotificationBell() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: notificationApi.list, refetchInterval: 60_000 });
  const unread = data?.unread ?? 0;
  const label = unread ? t("notifications.bellUnread", { count: unread }) : t("notifications.title");

  return (
    <NavLink to="/notifications" className="bell" aria-label={label} title={label}>
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <path
          fill="currentColor"
          d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2Z"
        />
      </svg>
      {unread > 0 && <span className="bell__badge">{unread > 99 ? "99+" : unread}</span>}
    </NavLink>
  );
}

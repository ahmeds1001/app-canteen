import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { settingsApi } from "@/api/endpoints";

/** Public canteen settings, plus the deadlines in words ("minuit la veille", "09:00 le jour même"…).
 *  The admin can change every time (FR-46), so screens never write "midnight" themselves. */
export function useCanteenSettings() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["settings"], queryFn: settingsApi.public, staleTime: Infinity });
  const s = query.data;
  /** "HH:MM", or "minuit" for an end-of-day 23:59(:59). */
  const clock = (time: string) => (time.slice(0, 5) === "23:59" ? t("deadline.midnight") : time.slice(0, 5));
  const days = s?.cutoff_days ?? 1;
  const cutoff = t(days === 0 ? "deadline.sameDay" : days === 1 ? "deadline.dayBefore" : "deadline.daysBefore", {
    time: clock(s?.cutoff_time ?? "23:59:59"),
    days,
  });
  return { settings: s, clock, cutoff };
}

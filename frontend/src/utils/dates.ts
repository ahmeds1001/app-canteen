/** Date helpers. Dates from the API are "YYYY-MM-DD" in the company time zone. */

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fromIso(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function isoToday(): string {
  return toIso(new Date());
}

export function addDays(iso: string, days: number): string {
  const d = fromIso(iso);
  d.setDate(d.getDate() + days);
  return toIso(d);
}

/** Monday of the week containing `iso`. */
export function startOfWeek(iso: string): string {
  const day = fromIso(iso).getDay(); // 0 = Sunday
  return addDays(iso, day === 0 ? -6 : 1 - day);
}

/** Weekday number used by the backend settings: 0 = Monday … 6 = Sunday. */
export function weekdayIndex(iso: string): number {
  return (fromIso(iso).getDay() + 6) % 7;
}

export function formatDay(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long" }).format(fromIso(iso));
}

export function formatShortDate(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric" }).format(fromIso(iso));
}

/** "dim. 25 oct., 23:59" in the company time zone: the API sends ISO strings with the company offset,
 *  so we keep their wall-clock part instead of converting to the browser's zone. */
export function formatCompanyDateTime(isoDateTime: string, locale: string): string {
  const day = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "short" })
    .format(fromIso(isoDateTime.slice(0, 10)));
  return `${day}, ${isoDateTime.slice(11, 16)}`;
}

/** Date helpers. Dates from the API are "YYYY-MM-DD" in the company time zone. */

export function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function formatDay(iso: string, locale: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long" }).format(
    new Date(y, m - 1, d),
  );
}

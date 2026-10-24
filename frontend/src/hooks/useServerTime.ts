import { useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/api/endpoints";

/** Server time in the company time zone. Time rules follow the server, not the phone's clock
 *  (and in development the server clock may be shifted with `manage.py dev_clock`). */
export function useServerTime() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: settingsApi.health, refetchInterval: 30_000 });
  return { serverTime: data?.server_time, shifted: data?.clock_shifted ?? false };
}

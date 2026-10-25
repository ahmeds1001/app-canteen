import { useCallback, useEffect, useState } from "react";
import { pushApi } from "@/api/endpoints";

/** Phone push for this browser (spec §8). "unsupported" = no HTTPS, or a browser without Web Push
 *  (iPhone: only once the app is added to the home screen). */
export type PushState = "loading" | "unsupported" | "disabled_on_server" | "denied" | "off" | "on";

const supported = () =>
  typeof window !== "undefined" &&
  window.isSecureContext &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

/** The service worker is registered by vite-plugin-pwa; don't wait forever if it never is. */
async function registration(): Promise<ServiceWorkerRegistration | null> {
  const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), 5000));
  return Promise.race([navigator.serviceWorker.ready, timeout]);
}

function keyBytes(base64url: string): ArrayBuffer {
  const padded = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0)).buffer as ArrayBuffer;
}

export function usePush() {
  const [state, setState] = useState<PushState>("loading");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!supported()) return setState("unsupported");
    if (Notification.permission === "denied") return setState("denied");
    const reg = await registration();
    if (!reg) return setState("unsupported");
    setState((await reg.pushManager.getSubscription()) ? "on" : "off");
  }, []);

  useEffect(() => {
    refresh().catch(() => setState("unsupported"));
  }, [refresh]);

  const enable = useCallback(async () => {
    setBusy(true);
    try {
      const { enabled, public_key } = await pushApi.key();
      if (!enabled) return setState("disabled_on_server");
      if ((await Notification.requestPermission()) !== "granted") return setState("denied");
      const reg = await registration();
      if (!reg) return setState("unsupported");
      const subscription =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) }));
      await pushApi.subscribe(subscription.toJSON());
      setState("on");
    } finally {
      setBusy(false);
    }
  }, []);

  const disable = useCallback(async () => {
    setBusy(true);
    try {
      const subscription = await (await registration())?.pushManager.getSubscription();
      if (subscription) {
        await pushApi.unsubscribe(subscription.endpoint);
        await subscription.unsubscribe();
      }
      setState("off");
    } finally {
      setBusy(false);
    }
  }, []);

  return { state, busy, enable, disable };
}

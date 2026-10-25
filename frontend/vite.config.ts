import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["logo.png"],
      // Phone push notifications (spec §8): the push handler lives in public/push-sw.js.
      workbox: { importScripts: ["push-sw.js"] },
      // Service worker also in `npm run dev`, so push can be tried locally (localhost counts as secure).
      devOptions: { enabled: true },
      manifest: {
        name: "Cantine OVAGRI",
        short_name: "Cantine",
        description: "Réservation des repas de la cantine OVAGRI Groupe",
        lang: "fr",
        theme_color: "#0A6B28",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/",
        icons: [{ src: "logo.png", sizes: "300x300", type: "image/png", purpose: "any" }],
      },
    }),
  ],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    // IPv4 loopback: on Windows "localhost" binds only ::1, which a phone linked with `adb reverse` cannot reach.
    // Still this PC only; `npm run dev:lan` (--host) overrides it.
    host: "127.0.0.1",
    // changeOrigin: Django sees "localhost:8000" even when a phone opens the app by the PC's IP (`npm run dev:lan`).
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/media": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});

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
    proxy: { "/api": "http://localhost:8000", "/media": "http://localhost:8000" },
  },
});

// PWA: the web app manifest (vite-plugin-pwa). vite.config.ts uses it.
// The icon PNGs come from public/icon.svg and public/icon-maskable.svg.
import type { VitePWAOptions } from "vite-plugin-pwa";

const THEME_COLOR = "#171717";

export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: "autoUpdate",
  includeAssets: ["icon.svg", "apple-touch-icon.png"],
  manifest: {
    name: "Watch Tower",
    short_name: "WT",
    description: "Watches the containers of a home-lab server.",
    theme_color: THEME_COLOR,
    background_color: THEME_COLOR,
    display: "standalone",
    start_url: "/",
    icons: [
      { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
      { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
      { src: "pwa-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
};

// The PWA config (pwa.config.ts) and the icon files in public/.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "vitest";

import { pwaOptions } from "../pwa.config";

// Vitest runs in frontend/.
const publicFile = (name: string) => join(process.cwd(), "public", name);

/** The width and height from the IHDR chunk of a PNG file. */
function pngSize(name: string): string {
  const data = readFileSync(publicFile(name));
  expect(data.subarray(1, 4).toString()).toBe("PNG");
  return `${String(data.readUInt32BE(16))}x${String(data.readUInt32BE(20))}`;
}

test("the manifest has the app fields", () => {
  expect(pwaOptions.manifest).toMatchObject({
    name: "Watch Tower",
    short_name: "WT",
    theme_color: "#151923",
    background_color: "#151923",
    display: "standalone",
    start_url: "/",
  });
});

test("the manifest icons exist with their sizes, one of them maskable", () => {
  const icons = pwaOptions.manifest ? (pwaOptions.manifest.icons ?? []) : [];

  expect(icons.map((icon) => icon.sizes)).toEqual(["192x192", "512x512", "512x512"]);
  for (const icon of icons) expect(pngSize(icon.src)).toBe(icon.sizes);
  expect(icons.filter((icon) => icon.purpose === "maskable")).toHaveLength(1);
});

test("index.html has the favicon, the apple-touch-icon and the iOS meta tags", () => {
  const html = readFileSync(join(process.cwd(), "index.html"), "utf8");

  expect(html).toContain('<link rel="icon" href="/icon.svg" type="image/svg+xml" />');
  expect(html).toContain('<link rel="apple-touch-icon" href="/apple-touch-icon.png" />');
  expect(html).toContain('<meta name="apple-mobile-web-app-capable" content="yes" />');
  expect(html).toContain('<meta name="apple-mobile-web-app-title" content="Watch Tower" />');
  expect(html).toContain('<meta name="theme-color" content="#151923" />');
  expect(existsSync(publicFile("icon.svg"))).toBe(true);
  expect(pngSize("apple-touch-icon.png")).toBe("180x180");
});

test("the service worker caches the app shell only and never /api", () => {
  const workbox = pwaOptions.workbox ?? {};
  const denied = (path: string) => (workbox.navigateFallbackDenylist ?? []).some((rule) => rule.test(path));

  expect(workbox.navigateFallback).toBe("index.html");
  expect(denied("/api/stream")).toBe(true);
  expect(denied("/api/containers/web/logs.txt")).toBe(true);
  expect(denied("/containers/web")).toBe(false);
  expect(workbox.globPatterns).toEqual(["**/*.{html,js,css,svg,png,woff2}"]);
  expect(workbox.runtimeCaching).toBeUndefined();
});

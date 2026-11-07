// Fake window.matchMedia (jsdom has none). setup.ts sets a small screen before each test.
// A test calls setDesktop(true) to get a large screen. The code reads `matches` only.

/** Make each media query match on a large screen and fail on a small screen. */
export function setDesktop(desktop: boolean) {
  window.matchMedia = (query: string) => ({ matches: desktop, media: query }) as unknown as MediaQueryList;
}

// The title of the browser tab, for example "Logs · web · WT", so that the admin can tell the tabs apart.
import { useEffect } from "react";

/** Sets the tab title to the parts and "WT", from the most specific part to the least. */
export function usePageTitle(...parts: string[]) {
  const title = [...parts, "WT"].join(" · ");
  useEffect(() => {
    document.title = title;
  }, [title]);
}

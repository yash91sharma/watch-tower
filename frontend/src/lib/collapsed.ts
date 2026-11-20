// The groups that the admin collapsed on a page. The browser keeps them in localStorage
// under the key of the page, so each page has its own collapsed groups.
import { useState } from "react";

function read(key: string) {
  return JSON.parse(localStorage.getItem(key) ?? "[]") as string[];
}

/**
 * The collapsed group labels and a function that collapses or expands one group.
 * `open` is a label that starts expanded, also if it was collapsed (for example ?group=).
 */
export function useCollapsed(key: string, open?: string | null) {
  const [collapsed, setCollapsed] = useState(() => read(key).filter((label) => label !== open));

  function toggle(label: string) {
    const next = collapsed.includes(label) ? collapsed.filter((item) => item !== label) : [...collapsed, label];
    localStorage.setItem(key, JSON.stringify(next));
    setCollapsed(next);
  }

  return { isOpen: (label: string) => !collapsed.includes(label), toggle };
}

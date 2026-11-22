// The groups that the admin collapsed on a page. The browser keeps them in localStorage
// under the key of the page, so each page has its own collapsed groups.
import { useState } from "react";

function read(key: string) {
  return JSON.parse(localStorage.getItem(key) ?? "[]") as string[];
}

/**
 * The collapsed group labels and the functions that collapse or expand the groups.
 * `open` is a label that starts expanded, also if it was collapsed (for example ?group=).
 */
export function useCollapsed(key: string, open?: string | null) {
  const [collapsed, setCollapsed] = useState(() => read(key).filter((label) => label !== open));

  function save(next: string[]) {
    localStorage.setItem(key, JSON.stringify(next));
    setCollapsed(next);
  }

  function toggle(label: string) {
    save(collapsed.includes(label) ? collapsed.filter((item) => item !== label) : [...collapsed, label]);
  }

  return {
    isOpen: (label: string) => !collapsed.includes(label),
    toggle,
    /** Collapses all the groups of the page. `labels` are the labels of all its groups. */
    collapseAll: (labels: string[]) => {
      save(labels);
    },
    expandAll: () => {
      save([]);
    },
  };
}

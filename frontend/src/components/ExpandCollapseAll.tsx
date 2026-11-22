// The "Expand all" and "Collapse all" buttons of a page with app groups.
import { ChevronsDownUp, ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ExpandCollapseAll({ onExpand, onCollapse }: { onExpand: () => void; onCollapse: () => void }) {
  return (
    <div className="flex items-center gap-1">
      <Button size="sm" variant="ghost" onClick={onExpand}>
        <ChevronsUpDown aria-hidden />
        Expand all
      </Button>
      <Button size="sm" variant="ghost" onClick={onCollapse}>
        <ChevronsDownUp aria-hidden />
        Collapse all
      </Button>
    </div>
  );
}

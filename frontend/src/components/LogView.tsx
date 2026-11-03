// A virtual list of log lines. Follow mode keeps the end in view. Scroll up pauses it.
import { useVirtualizer } from "@tanstack/react-virtual";
import { useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { LogLine } from "@/lib/logs";
import { cn } from "@/lib/utils";

const ROW_HEIGHT = 20;

export function LogView({ lines }: { lines: LogLine[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  // The build has no React Compiler, so its memoization warning does not apply.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: lines.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    getItemKey: (index) => lines[index]?.id ?? index,
    overscan: 20,
  });

  useLayoutEffect(() => {
    const element = scrollRef.current;
    // The browser limits scrollTop to the end.
    if (follow && element) element.scrollTop = element.scrollHeight;
  }, [follow, lines]);

  function onScroll() {
    const element = scrollRef.current;
    if (!element) return;
    // At the end: follow. Above the end (the user scrolled up): pause.
    setFollow(element.scrollTop + element.clientHeight >= element.scrollHeight - ROW_HEIGHT / 2);
  }

  return (
    <div className="relative">
      <div
        ref={scrollRef}
        role="log"
        aria-label="Log lines"
        // A fast log must not flood screen readers.
        aria-live="off"
        tabIndex={0}
        onScroll={onScroll}
        className="h-[70svh] overflow-auto rounded-lg border bg-muted/30 font-mono text-xs"
      >
        <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((item) => {
            const line = lines[item.index];
            if (!line) return null;
            return (
              <div
                key={item.key}
                data-index={item.index}
                ref={virtualizer.measureElement}
                className={cn(
                  "absolute top-0 left-0 w-full px-2 leading-5 break-all whitespace-pre-wrap",
                  line.stream === "stderr" && "text-destructive",
                )}
                style={{ transform: `translateY(${String(item.start)}px)` }}
              >
                {line.text}
              </div>
            );
          })}
        </div>
      </div>
      {!follow && (
        <Button
          size="sm"
          className="absolute right-4 bottom-4"
          onClick={() => {
            setFollow(true);
          }}
        >
          Follow
        </Button>
      )}
    </div>
  );
}

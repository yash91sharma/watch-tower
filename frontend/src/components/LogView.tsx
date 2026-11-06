// A virtual list of log lines. Follow mode keeps the end in view. Scroll up or Pause stops it.
// Search: the matches of the query are marked, and the current match line is shown.
// Pretty: JSON object lines show formatted (rows have their own height).
import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useEffectEvent, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { highlight, type LogLine, prettyJson } from "@/lib/logs";
import { cn } from "@/lib/utils";

const ROW_HEIGHT = 20;

export function LogView({
  lines,
  query = "",
  currentId = null,
  pretty = false,
}: {
  lines: LogLine[];
  query?: string;
  currentId?: number | null;
  pretty?: boolean;
}) {
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

  // Go to the current match (a new search, next or previous). This pauses follow.
  const showLine = useEffectEvent((id: number) => {
    const index = lines.findIndex((line) => line.id === id);
    if (index === -1) return;
    setFollow(false);
    virtualizer.scrollToIndex(index, { align: "center" });
  });
  useEffect(() => {
    if (currentId !== null) showLine(currentId);
  }, [currentId]);

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
                  item.index % 2 === 1 && "bg-muted/60",
                  line.stream === "stderr" && "text-destructive",
                  line.id === currentId && "bg-accent",
                )}
                style={{ transform: `translateY(${String(item.start)}px)` }}
              >
                {highlight(pretty ? prettyJson(line.text) : line.text, query).map((part, index) =>
                  part.match ? (
                    <mark key={index} className="rounded-sm bg-yellow-200 text-black">
                      {part.text}
                    </mark>
                  ) : (
                    part.text
                  ),
                )}
              </div>
            );
          })}
        </div>
      </div>
      <Button
        size="sm"
        variant={follow ? "outline" : "default"}
        className="absolute right-4 bottom-4"
        onClick={() => {
          setFollow(!follow);
        }}
      >
        {follow ? "Pause" : "Follow"}
      </Button>
    </div>
  );
}

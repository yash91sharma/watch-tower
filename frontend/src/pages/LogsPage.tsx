// The live log of a container, with search and JSON pretty-print (in the browser) and a tail size.
// All controls are in one toolbar above the log.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Download } from "lucide-react";
import { useParams } from "react-router";

import { containerQuery } from "@/api/queries";
import { useLogStream } from "@/api/useLogStream";
import { Breadcrumb } from "@/components/Breadcrumb";
import { FormError } from "@/components/FormError";
import { LogView } from "@/components/LogView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { matchingLines } from "@/lib/logs";
import { usePageTitle } from "@/lib/pageTitle";

const TAIL_SIZES = [100, 500, 1000, 5000, 10000];

export function LogsPage() {
  const { name = "" } = useParams();
  usePageTitle("Logs", name);
  const [tail, setTail] = useState(500);
  const { lines, error } = useLogStream(name, tail);
  // The container: its API error (for example "No container") says why the log stops.
  const { error: containerError } = useQuery(containerQuery(name));
  const [query, setQuery] = useState("");
  const [onlyMatches, setOnlyMatches] = useState(false);
  const [position, setPosition] = useState(0);
  const [pretty, setPretty] = useState(false);

  const matches = useMemo(() => matchingLines(lines, query), [lines, query]);
  // The buffer can drop old lines, so keep the position in the range.
  const current = matches.length > 0 ? Math.min(position, matches.length - 1) : 0;

  const move = (step: number) => {
    if (matches.length > 0) setPosition((current + step + matches.length) % matches.length);
  };

  return (
    <div className="space-y-3">
      <Breadcrumb
        crumbs={[{ label: "Apps", to: "/apps" }, { label: name, to: `/containers/${name}` }, { label: "Logs" }]}
      />
      <h1 className="text-xl font-semibold break-all">Logs: {name}</h1>
      {/* One row: search, the view toggles, then the tail size and the download at the end. */}
      <div role="toolbar" aria-label="Log controls" className="flex flex-wrap items-center gap-2 text-sm">
        <LogSearch
          query={query}
          onQueryChange={(value) => {
            setQuery(value);
            setPosition(0);
          }}
          matchCount={matches.length}
          current={current}
          onMove={move}
        />
        <span aria-hidden className="mx-1 h-5 w-px bg-border max-sm:hidden" />
        <Toggle label="Only matches" pressed={onlyMatches} onChange={setOnlyMatches} />
        <Toggle label="Format JSON" pressed={pretty} onChange={setPretty} />
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-2">
            Tail
            <select
              className="h-8 rounded-lg border bg-transparent px-2"
              value={tail}
              onChange={(event) => {
                setTail(Number(event.target.value));
              }}
            >
              {TAIL_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <Button asChild size="sm" variant="outline">
            <a href={`/api/containers/${encodeURIComponent(name)}/logs.txt`} download>
              <Download aria-hidden />
              Download
            </a>
          </Button>
        </div>
      </div>
      <FormError error={containerError ?? error} />
      <LogView
        lines={onlyMatches && query ? matches : lines}
        query={query}
        currentId={matches[current]?.id ?? null}
        pretty={pretty}
      />
    </div>
  );
}

// The search input, the match count and the buttons to go to the previous or next match.
// Keys in the input: Enter = next match, Shift+Enter = previous match, Escape = clear.
function LogSearch({
  query,
  onQueryChange,
  matchCount,
  current,
  onMove,
}: {
  query: string;
  onQueryChange: (query: string) => void;
  matchCount: number;
  current: number;
  onMove: (step: number) => void;
}) {
  return (
    <>
      <Input
        aria-label="Search"
        type="search"
        placeholder="Search"
        className="w-48"
        value={query}
        onChange={(event) => {
          onQueryChange(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            onMove(event.shiftKey ? -1 : 1);
          } else if (event.key === "Escape") {
            event.preventDefault();
            onQueryChange("");
          }
        }}
      />
      {query && (
        <span aria-live="polite" className="text-muted-foreground">
          {matchCount === 0 ? "No match" : `${String(current + 1)} of ${String(matchCount)}`}
        </span>
      )}
      <Button
        size="icon-sm"
        variant="outline"
        aria-label="Previous match"
        title="Previous match (Shift+Enter)"
        disabled={matchCount === 0}
        onClick={() => {
          onMove(-1);
        }}
      >
        <ChevronUp aria-hidden />
      </Button>
      <Button
        size="icon-sm"
        variant="outline"
        aria-label="Next match"
        title="Next match (Enter)"
        disabled={matchCount === 0}
        onClick={() => {
          onMove(1);
        }}
      >
        <ChevronDown aria-hidden />
      </Button>
    </>
  );
}

/** An on/off button. It has the filled look when it is on. */
function Toggle({ label, pressed, onChange }: { label: string; pressed: boolean; onChange: (pressed: boolean) => void }) {
  return (
    <Button
      size="sm"
      variant={pressed ? "secondary" : "outline"}
      aria-pressed={pressed}
      className="aria-pressed:border-primary/40"
      onClick={() => {
        onChange(!pressed);
      }}
    >
      {label}
    </Button>
  );
}

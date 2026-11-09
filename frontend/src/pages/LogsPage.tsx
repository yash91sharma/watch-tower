// The live log of a container, with search and JSON pretty-print (in the browser) and a tail size.
import { useMemo, useState } from "react";
import { useParams } from "react-router";

import { useLogStream } from "@/api/useLogStream";
import { Breadcrumb } from "@/components/Breadcrumb";
import { FormError } from "@/components/FormError";
import { LogView } from "@/components/LogView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { matchingLines } from "@/lib/logs";

const TAIL_SIZES = [100, 500, 1000, 5000, 10000];

export function LogsPage() {
  const { name = "" } = useParams();
  const [tail, setTail] = useState(500);
  const { lines, error } = useLogStream(name, tail);
  const [query, setQuery] = useState("");
  const [onlyMatches, setOnlyMatches] = useState(false);
  const [position, setPosition] = useState(0);
  const [pretty, setPretty] = useState(false);

  const matches = useMemo(() => matchingLines(lines, query), [lines, query]);
  // The buffer can drop old lines, so keep the position in the range.
  const current = matches.length > 0 ? Math.min(position, matches.length - 1) : 0;

  return (
    <div className="space-y-3">
      <Breadcrumb
        crumbs={[{ label: "Containers", to: "/" }, { label: name, to: `/containers/${name}` }, { label: "Logs" }]}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold break-all">Logs: {name}</h1>
        <div className="flex items-center gap-2">
          <Button asChild size="sm" variant="outline">
            <a href={`/api/containers/${encodeURIComponent(name)}/logs.txt`} download>
              Download
            </a>
          </Button>
          <label className="flex items-center gap-2 text-sm">
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
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <LogSearch
          query={query}
          onQueryChange={(value) => {
            setQuery(value);
            setPosition(0);
          }}
          matchCount={matches.length}
          current={current}
          onMove={(step) => {
            setPosition((current + step + matches.length) % matches.length);
          }}
        />
        <Checkbox label="Only matches" checked={onlyMatches} onChange={setOnlyMatches} />
        <Checkbox label="Format JSON" checked={pretty} onChange={setPretty} />
      </div>
      <FormError error={error} />
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
      />
      {query && (
        <span aria-live="polite" className="text-muted-foreground">
          {matchCount === 0 ? "No match" : `${String(current + 1)} of ${String(matchCount)}`}
        </span>
      )}
      <Button
        size="sm"
        variant="outline"
        aria-label="Previous match"
        disabled={matchCount === 0}
        onClick={() => {
          onMove(-1);
        }}
      >
        ↑
      </Button>
      <Button
        size="sm"
        variant="outline"
        aria-label="Next match"
        disabled={matchCount === 0}
        onClick={() => {
          onMove(1);
        }}
      >
        ↓
      </Button>
    </>
  );
}

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center gap-1.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
      {label}
    </label>
  );
}

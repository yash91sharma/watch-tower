// The live log of a container, with search and JSON pretty-print (in the browser) and a tail size.
import { useMemo, useState } from "react";
import { useParams } from "react-router";

import { useLogStream } from "@/api/useLogStream";
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
  const move = (step: number) => {
    setPosition((current + step + matches.length) % matches.length);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold break-all">Logs: {name}</h1>
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
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Input
          aria-label="Search"
          type="search"
          placeholder="Search"
          className="w-48"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPosition(0);
          }}
        />
        {query && (
          <span aria-live="polite" className="text-muted-foreground">
            {matches.length === 0 ? "No match" : `${String(current + 1)} of ${String(matches.length)}`}
          </span>
        )}
        <Button
          size="sm"
          variant="outline"
          aria-label="Previous match"
          disabled={matches.length === 0}
          onClick={() => {
            move(-1);
          }}
        >
          ↑
        </Button>
        <Button
          size="sm"
          variant="outline"
          aria-label="Next match"
          disabled={matches.length === 0}
          onClick={() => {
            move(1);
          }}
        >
          ↓
        </Button>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={onlyMatches}
            onChange={(event) => {
              setOnlyMatches(event.target.checked);
            }}
          />
          Only matches
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={pretty}
            onChange={(event) => {
              setPretty(event.target.checked);
            }}
          />
          Format JSON
        </label>
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

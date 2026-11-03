// The live log of a container.
import { useState } from "react";
import { useParams } from "react-router";

import { useLogStream } from "@/api/useLogStream";
import { FormError } from "@/components/FormError";
import { LogView } from "@/components/LogView";

const TAIL_SIZES = [100, 500, 1000, 5000, 10000];

export function LogsPage() {
  const { name = "" } = useParams();
  const [tail, setTail] = useState(500);
  const { lines, error } = useLogStream(name, tail);

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
      <FormError error={error} />
      <LogView lines={lines} />
    </div>
  );
}

// A time as "5 minutes ago", with the full time on hover. The text changes each minute.
import { useEffect, useState } from "react";

import { formatAgo, formatTime } from "@/lib/time";

export function RelativeTime({ iso }: { iso: string }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 60_000);
    return () => {
      clearInterval(timer);
    };
  }, []);
  return (
    <time dateTime={iso} title={formatTime(iso)}>
      {formatAgo(iso, now)}
    </time>
  );
}

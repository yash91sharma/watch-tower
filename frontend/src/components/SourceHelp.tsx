// The (i) button of the release source: a small popup that tells what URL to enter, with
// one example for each source kind. Static help text: the API checks the value.
import { Info } from "lucide-react";
import { Popover } from "radix-ui";

import { Button } from "@/components/ui/button";

const KINDS = [
  { name: "GitHub", use: "The app has releases on GitHub.", example: "https://github.com/immich-app/immich" },
  {
    name: "Docker Hub",
    use: "The app has no GitHub releases. WT reads the image tags.",
    example: "https://hub.docker.com/r/searxng/searxng",
  },
];

export function SourceHelp() {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="What to enter" title="What to enter">
          <Info aria-hidden />
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          role="dialog"
          aria-label="What to enter"
          align="end"
          sideOffset={4}
          className="z-50 w-[min(22rem,calc(100vw-2rem))] space-y-3 rounded-lg border bg-card p-4 text-sm shadow-lg"
        >
          <p className="font-medium">What to enter</p>
          {KINDS.map((kind) => (
            <div key={kind.name} className="space-y-0.5">
              <p>
                <span className="font-medium">{kind.name}:</span> {kind.use}
              </p>
              <code className="block font-mono text-xs break-all text-muted-foreground">{kind.example}</code>
            </div>
          ))}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

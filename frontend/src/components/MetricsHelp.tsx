// The (i) button of the Overview: a dialog that tells, for each VM tile, what the value is,
// how to read it and why it matters on a home-lab server. Static help text: the values and
// labels come from the API. The header with the X stays at the top; only the list scrolls.
import { Info, X } from "lucide-react";
import { Dialog } from "radix-ui";

import { Button } from "@/components/ui/button";

interface HelpItem {
  // The tile title on the Overview.
  title: string;
  // One sentence: what the value is.
  what: string;
  // One sentence: what a normal value is, and when to look closer.
  read: string;
  // One sentence: why it is important to monitor on a home-lab server.
  why: string;
}

const HELP: HelpItem[] = [
  {
    title: "CPU",
    what: "How busy the VM CPU cores are, as a percent of all cores.",
    read: "Short peaks are normal; above 80% for a long time means that an app uses too much CPU or the VM needs more cores.",
    why: "A CPU that is always full makes every app on the server slow.",
  },
  {
    title: "Memory",
    what: "The memory that apps use in the VM, without the cache that Linux can free.",
    read: "Near 100%, with swap that goes up, means that the VM needs more memory.",
    why: "When memory is full, Linux stops (kills) apps with no warning.",
  },
  {
    title: "Swap",
    what: "The disk space that Linux uses for memory that does not fit in RAM.",
    read: "A small, steady value is normal; a value that goes up means that the VM has too little memory.",
    why: "Apps that use swap become slow, because a disk is much slower than RAM.",
  },
  {
    title: "Disk",
    what: "The used space on the VM disk that holds the images, containers and volumes.",
    read: "Above 85%, remove old images and build cache (docker system prune).",
    why: "A full disk stops apps and can corrupt databases.",
  },
  {
    title: "Disk I/O",
    what: "The data that the VM reads from and writes to its disks, per second.",
    read: "Peaks during starts, backups and updates are normal; a high write rate that does not stop is often an app that writes too many logs.",
    why: "Too much disk I/O makes all apps slow and wears out SSDs.",
  },
  {
    title: "Network",
    what: "The data that all containers receive (in) and send (out), per second.",
    read: "Short peaks from downloads and streams are normal; a high out value that you do not expect means that an app sends data.",
    why: "An upload that you do not expect can be a bad backup job or an app that an attacker controls.",
  },
  {
    title: "Load",
    what: "The number of processes that run or wait, as an average over 1, 5 and 15 minutes.",
    read: "A value above the number of cores means that processes wait.",
    why: "High load with low CPU often points to a slow or failing disk.",
  },
  {
    title: "Uptime",
    what: "The time since the VM last started.",
    read: "A low value that you do not expect means that the VM or the Mac restarted.",
    why: "Restarts that you did not plan can show power, crash or update problems.",
  },
];

export function MetricsHelp() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="What the metrics mean" title="What the metrics mean">
          <Info aria-hidden />
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[85svh] w-[min(42rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border bg-card shadow-lg">
          <div className="flex items-start gap-3 border-b p-5 pb-4">
            <div className="flex-1 space-y-1">
              <Dialog.Title className="text-lg font-semibold">How to read the metrics</Dialog.Title>
              <Dialog.Description className="text-sm text-muted-foreground">
                The values are for the Docker VM (on OrbStack, the OrbStack VM), not the Mac.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Close" title="Close">
                <X aria-hidden />
              </Button>
            </Dialog.Close>
          </div>
          <div className="space-y-4 overflow-y-auto p-5 pt-4">
            {HELP.map((item) => (
              <section key={item.title} className="space-y-1 text-sm">
                <h3 className="font-medium">{item.title}</h3>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  <dt className="text-muted-foreground">What</dt>
                  <dd>{item.what}</dd>
                  <dt className="text-muted-foreground">Read</dt>
                  <dd>{item.read}</dd>
                  <dt className="text-muted-foreground">Why</dt>
                  <dd>{item.why}</dd>
                </dl>
              </section>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

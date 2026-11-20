// The (i) button of the Overview: a dialog that tells what each metric is (how WT gets it)
// and how an admin reads it. Static help text: the values and labels come from the API.
import { Info } from "lucide-react";
import { Dialog } from "radix-ui";

import { Button } from "@/components/ui/button";

interface HelpItem {
  title: string;
  // What the value is, and how WT gets it.
  what: string;
  // What a normal value is, and when to look closer.
  read: string;
}

const HELP: HelpItem[] = [
  {
    title: "CPU",
    what: "The part of all VM cores that is busy (not idle and not waiting for the disk), as an average over the poll interval. 100% means that all cores are busy. The cores in the label are the same value in cores: \"25% (2.5 cores)\" on 10 cores. For a container, the value is its part of all VM cores, from the Docker stats.",
    read: "Short peaks are normal. A VM that stays above about 80% for a long time has too little CPU: find the busy app in the list, or give OrbStack more cores. One app process can use at most 1 core, so a container at \"1.0 core\" can be at its limit even when the VM is not.",
  },
  {
    title: "Memory",
    what: "VM: MemTotal minus MemAvailable from /proc/meminfo. On OrbStack, the total is the memory limit in the OrbStack settings, and OrbStack gives the free memory back to macOS. \"Containers\" is the sum of the shown containers. A container uses its memory minus the inactive file cache (the same as docker stats), of its memory limit or of the VM total if it has no limit.",
    read: "The Linux cache uses free memory, but MemAvailable does not count the cache that Linux can free, so the value is the memory that is really in use. A VM near its total, with swap that increases, needs more memory or an app that uses less. A container near its own limit can be stopped by the kernel (out of memory).",
  },
  {
    title: "Swap",
    what: "The swap space of the VM that is in use, of its total (/proc/meminfo).",
    read: "A small, steady value is normal: Linux moves unused memory to swap. Swap that increases, together with high disk I/O, shows that the VM has too little memory.",
  },
  {
    title: "Disk",
    what: "The used space of the VM disk that holds the Docker data (images, containers, volumes, the WT data).",
    read: "Above about 85%, free some space: remove old images and build cache (docker system prune), or check the log size of the apps. A full disk stops apps and can damage their data.",
  },
  {
    title: "Disk I/O",
    what: "The bytes per second that the VM reads from and writes to its disks (all virtual disks, also swap), from /proc/diskstats.",
    read: "Peaks at a start, a backup or an update are normal. A high write rate that does not stop can be an app that writes too many logs, or swap. Compare it with the Swap value.",
  },
  {
    title: "Network",
    what: "The bytes per second that the containers get (in) and send (out): the sum of the shown containers. WT has its own network, so it cannot see the full VM network. Containers with host networking are not in the sum.",
    read: "Downloads and streams give high values for a short time. A high \"out\" value that you do not expect can be an app that uploads data: find it in the list.",
  },
  {
    title: "Load",
    what: "The average number of processes that run or wait for the CPU or the disk, over the last 1, 5 and 15 minutes (/proc/loadavg).",
    read: "Compare it with the number of cores (in the CPU label). A load below the number of cores is OK. A load above it for a long time means that processes wait. If the 1-minute value is higher than the 15-minute value, the load increases.",
  },
  {
    title: "Uptime",
    what: "The time since the VM started.",
    read: "It starts again at 0 when OrbStack or the Mac restarts. A short uptime that you do not expect shows a restart.",
  },
  {
    title: "Apps and containers",
    what: "An app is a Compose project, or a container with no project. The counts and the list have the containers that WT shows (not the ones with the label wt.enable=false). A stopped container has no values (\"-\"). The group values are the sums of their containers.",
    read: "Fewer running containers than you expect: open App details and look at the state and the health.",
  },
  {
    title: "Graphs and sparklines",
    what: "WT gets the values at the metrics interval on the Settings page and saves one average for each minute. The 1 hour to 24 hours ranges show minutes, 7 days shows 15-minute averages, and 30 days shows 1-hour averages. The sparklines show the last hour. A gap is a time with no value (WT did not run, or the container did not run).",
    read: "An average makes short peaks smaller, so the longer ranges show trends, not peaks. Move the pointer on a graph to see its values. A range change in one graph changes all graphs.",
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
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[85svh] w-[min(42rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 space-y-4 overflow-y-auto rounded-xl border bg-card p-5 shadow-lg">
          <Dialog.Title className="text-lg font-semibold">How to read the metrics</Dialog.Title>
          <Dialog.Description className="text-sm text-muted-foreground">
            The Docker VM is the Linux VM that runs the containers (on OrbStack, the OrbStack VM), not the Mac.
          </Dialog.Description>
          {HELP.map((item) => (
            <section key={item.title} className="space-y-1 text-sm">
              <h3 className="font-medium">{item.title}</h3>
              <p>{item.what}</p>
              <p>
                <span className="font-medium">How to read it</span>: {item.read}
              </p>
            </section>
          ))}
          <div className="flex justify-end">
            <Dialog.Close asChild>
              <Button variant="outline">Close</Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

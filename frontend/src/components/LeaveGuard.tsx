// Asks before the admin leaves a page with unsaved changes.
// A link in WT opens a dialog (Stay or Leave). A reload or a close of the tab opens the
// dialog of the browser.
import { AlertDialog } from "radix-ui";
import { useEffect } from "react";
import { useBlocker } from "react-router";

import { Button } from "@/components/ui/button";

export function LeaveGuard({ when }: { when: boolean }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => when && currentLocation.pathname !== nextLocation.pathname);

  useEffect(() => {
    if (!when) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [when]);

  return (
    <AlertDialog.Root open={blocker.state === "blocked"}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <AlertDialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-xl border bg-card p-5 shadow-lg">
          <AlertDialog.Title className="text-lg font-semibold">Leave without saving?</AlertDialog.Title>
          <AlertDialog.Description className="text-sm text-muted-foreground">
            The changes on this page are not saved. If you leave, you lose them.
          </AlertDialog.Description>
          <div className="flex justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <Button variant="outline" onClick={() => blocker.reset?.()}>
                Stay
              </Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <Button variant="destructive" onClick={() => blocker.proceed?.()}>
                Leave
              </Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}

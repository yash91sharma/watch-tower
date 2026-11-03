// Config export and import. Import: read the file, send it to the dry run, show the
// counts and errors, and import it only after the admin confirms.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ChangeEvent } from "react";

import { api, ApiError, unwrap } from "@/api/client";
import { settingsQuery } from "@/api/queries";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";

const plural = (count: number, one: string, many: string) => `${String(count)} ${count === 1 ? one : many}`;

export function ConfigFile() {
  const queryClient = useQueryClient();
  const id = useId();
  const [config, setConfig] = useState<unknown>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  // A new key empties the file input, so that the same file can be chosen again.
  const [inputKey, setInputKey] = useState(0);

  const importConfig = async (body: unknown, dryRun: boolean) =>
    unwrap(await api.POST("/api/config/import", { params: { query: { dry_run: dryRun } }, body: body as never }));
  const check = useMutation({ mutationFn: (body: unknown) => importConfig(body, true) });
  const save = useMutation({
    mutationFn: (body: unknown) => importConfig(body, false),
    onSuccess: async () => {
      done();
      // The settings form shows the new values after a new load.
      await queryClient.resetQueries({ queryKey: settingsQuery.queryKey });
      await queryClient.invalidateQueries({ queryKey: ["containers"] });
    },
  });

  function done() {
    setConfig(null);
    check.reset();
    setInputKey((key) => key + 1);
  }

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    save.reset();
    check.reset();
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setFileError("The file is not JSON.");
      return;
    }
    setFileError(null);
    setConfig(parsed);
    check.mutate(parsed);
  }

  const result = check.data;
  const dryRunError =
    result && !result.valid ? new ApiError(422, "The file has errors.", { fields: result.errors }) : null;

  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="font-medium">
        Export and import
      </h2>
      <p className="text-sm text-muted-foreground">
        The file has the settings and the release sources. It has no secrets.
      </p>
      <Button asChild variant="outline" size="sm">
        <a href="/api/config/export" download>
          Export
        </a>
      </Button>
      <Field
        key={inputKey}
        label="Config file"
        type="file"
        accept="application/json,.json"
        onChange={(event) => void onFile(event)}
      />
      <FormError error={fileError ?? dryRunError ?? check.error ?? save.error} />
      {result?.valid && (
        <div className="space-y-2 text-sm">
          <p>
            {plural(result.settings, "setting", "settings")},{" "}
            {plural(result.containers_added, "new container", "new containers")},{" "}
            {plural(result.containers_updated, "changed container", "changed containers")}.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={save.isPending}
              onClick={() => {
                save.mutate(config);
              }}
            >
              Import
            </Button>
            <Button size="sm" variant="outline" onClick={done}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {save.isSuccess && (
        <p role="status" className="text-sm text-muted-foreground">
          Imported.
        </p>
      )}
    </section>
  );
}

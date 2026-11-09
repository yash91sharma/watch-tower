// The release source of a container: show it, confirm it, or edit it.
// A saved edit is confirmed. An empty value clears the source.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { api, unwrap } from "@/api/client";
import { containersQuery } from "@/api/queries";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { Section } from "@/components/Section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function ReleaseSource({ name, source, confirmed }: { name: string; source: string | null; confirmed: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");

  const save = useMutation({
    mutationFn: async (body: { source: string | null; confirmed: boolean }) =>
      unwrap(await api.PUT("/api/containers/{name}/release-source", { params: { path: { name } }, body })),
    onSuccess: async () => {
      setEditing(false);
      // The status and the latest version can change too.
      await queryClient.invalidateQueries({ queryKey: containersQuery.queryKey });
    },
  });

  function onSave(event: SubmitEvent) {
    event.preventDefault();
    save.mutate({ source: value.trim() || null, confirmed: true });
  }

  return (
    <Section title="Release source">
      {editing ? (
        <form className="space-y-3" onSubmit={onSave}>
          <Field
            label="GitHub URL or owner/repo"
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
            }}
          />
          <p className="text-sm text-muted-foreground">Leave it empty to clear the source. WT then does no check.</p>
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={save.isPending}>
              Save
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setEditing(false);
                save.reset();
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="break-all">{source ?? "No release source"}</span>
          {!confirmed && <Badge variant="outline">not confirmed</Badge>}
          {!confirmed && source !== null && (
            <Button
              size="sm"
              disabled={save.isPending}
              onClick={() => {
                save.mutate({ source, confirmed: true });
              }}
            >
              Confirm
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setValue(source ?? "");
              save.reset();
              setEditing(true);
            }}
          >
            Edit
          </Button>
        </div>
      )}
      <FormError error={save.error} />
    </Section>
  );
}

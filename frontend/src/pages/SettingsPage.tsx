// Settings: the UI settings form, a test ntfy message, the secret state (env vars set the secrets), export and import.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { api, unwrap } from "@/api/client";
import { settingsQuery } from "@/api/queries";
import type { SecretState, Settings } from "@/api/types";
import { ConfigFile } from "@/components/ConfigFile";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { QueryPending } from "@/components/QueryPending";
import { Section } from "@/components/Section";
import { Button } from "@/components/ui/button";

const FIELDS: { key: keyof Settings; label: string; numeric?: boolean }[] = [
  { key: "check_interval_hours", label: "Check interval (hours)", numeric: true },
  { key: "restart_count", label: "Restart loop: restarts", numeric: true },
  { key: "restart_window_minutes", label: "Restart loop: window (minutes)", numeric: true },
  { key: "ntfy_url", label: "ntfy URL" },
  { key: "ntfy_topic", label: "ntfy topic" },
  { key: "llm_url", label: "LLM URL" },
  { key: "llm_model", label: "LLM model" },
  { key: "public_url", label: "WT URL (for links in notifications)" },
];

const SECRETS: { key: keyof SecretState; label: string }[] = [
  { key: "github_token", label: "GitHub token" },
  { key: "ntfy_token", label: "ntfy token" },
  { key: "llm_api_key", label: "LLM API key" },
];

export function SettingsPage() {
  const { data, error } = useQuery(settingsQuery);
  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold">Settings</h1>
      {data === undefined ? (
        <QueryPending error={error} />
      ) : (
        <>
          <SettingsForm values={data.values} />
          <Secrets secrets={data.secrets} />
        </>
      )}
      <ConfigFile />
    </div>
  );
}

function SettingsForm({ values }: { values: Settings }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() =>
    Object.fromEntries(FIELDS.map(({ key }) => [key, String(values[key] ?? "")])),
  );
  const save = useMutation({
    // The form sends the text of each input. The backend validates and converts the
    // values (for example "24" to 24, "" to null) and gives an error per field.
    mutationFn: async () => unwrap(await api.PUT("/api/settings", { body: form as unknown as Settings })),
    onSuccess: (result) => {
      queryClient.setQueryData(settingsQuery.queryKey, result);
    },
  });
  // Sends a test message with the form values. It does not save them.
  const sendTest = useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/settings/ntfy-test", { body: form as unknown as Settings }));
    },
  });

  function onSubmit(event: SubmitEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      {FIELDS.map(({ key, label, numeric }) => (
        <Field
          key={key}
          label={label}
          inputMode={numeric ? "numeric" : undefined}
          value={form[key]}
          onChange={(event) => {
            setForm({ ...form, [key]: event.target.value });
            save.reset();
            sendTest.reset();
          }}
        />
      ))}
      <FormError error={save.error} />
      <FormError error={sendTest.error} />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          Save
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={sendTest.isPending}
          onClick={() => {
            sendTest.mutate();
          }}
        >
          Send test notification
        </Button>
        {save.isSuccess && (
          <span role="status" className="text-sm text-muted-foreground">
            Saved.
          </span>
        )}
        {sendTest.isSuccess && (
          <span role="status" className="text-sm text-muted-foreground">
            Sent. Look for it in ntfy.
          </span>
        )}
      </div>
    </form>
  );
}

function Secrets({ secrets }: { secrets: SecretState }) {
  return (
    <Section title="Secrets">
      <p className="text-sm text-muted-foreground">Env vars set the secrets. Restart WT after a change.</p>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-sm">
        {SECRETS.map(({ key, label }) => [
          <dt key={`${key}-label`} className="text-muted-foreground">
            {label}
          </dt>,
          <dd key={key}>{secrets[key]}</dd>,
        ])}
      </dl>
    </Section>
  );
}

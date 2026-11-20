// Settings: the UI settings form, a test ntfy message, the secret state (env vars set the secrets), export and import.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SubmitEvent } from "react";

import { api, unwrap } from "@/api/client";
import { settingsQuery } from "@/api/queries";
import type { SecretState, Settings } from "@/api/types";
import { ConfigFile } from "@/components/ConfigFile";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { QueryPending } from "@/components/QueryPending";
import { Section } from "@/components/Section";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

// A field with `options` is a select. The options are the values that the backend accepts.
const FIELDS: { key: keyof Settings; label: string; numeric?: boolean; options?: Settings["metrics_interval_seconds"][] }[] = [
  { key: "check_interval_hours", label: "Check interval (hours)", numeric: true },
  { key: "restart_count", label: "Restart loop: restarts", numeric: true },
  { key: "restart_window_minutes", label: "Restart loop: window (minutes)", numeric: true },
  { key: "ntfy_url", label: "ntfy URL" },
  { key: "ntfy_topic", label: "ntfy topic" },
  { key: "llm_url", label: "LLM URL" },
  { key: "llm_model", label: "LLM model" },
  { key: "public_url", label: "WT URL (for links in notifications)" },
  { key: "metrics_interval_seconds", label: "Metrics interval (seconds)", options: [5, 10, 15, 30, 60] },
];

// The label of each field, for the field errors of the API.
const LABELS: Record<string, string> = Object.fromEntries(FIELDS.map(({ key, label }) => [key, label]));

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
  // The form sends the text of each input. The backend validates and converts the
  // values (for example "24" to 24, "" to null) and gives an error per field.
  const body = form as unknown as Settings;
  const save = useMutation({
    mutationFn: async () => unwrap(await api.PUT("/api/settings", { body })),
    onSuccess: (result) => {
      queryClient.setQueryData(settingsQuery.queryKey, result);
    },
  });
  // Sends a test message with the form values. It does not save them.
  const sendTest = useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/settings/ntfy-test", { body }));
    },
  });

  function onSubmit(event: SubmitEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      {FIELDS.map(({ key, label, numeric, options }) => {
        const onChange = (event: { target: { value: string } }) => {
          setForm({ ...form, [key]: event.target.value });
          save.reset();
          sendTest.reset();
        };
        return options ? (
          <SelectField key={key} label={label} value={form[key]} options={options} onChange={onChange} />
        ) : (
          <Field key={key} label={label} inputMode={numeric ? "numeric" : undefined} value={form[key]} onChange={onChange} />
        );
      })}
      <FormError error={save.error} labels={LABELS} />
      <FormError error={sendTest.error} labels={LABELS} />
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

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | undefined;
  options: number[];
  onChange: (event: { target: { value: string } }) => void;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select id={id} value={value} onChange={onChange} className="h-8 rounded-lg border bg-background px-2 text-sm">
        {options.map((option) => (
          <option key={option} value={String(option)}>
            {option}
          </option>
        ))}
      </select>
    </div>
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

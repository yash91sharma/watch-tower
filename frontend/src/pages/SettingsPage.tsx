// Settings: the UI settings form, a test ntfy message, the secret state (env vars set the secrets), export and import.
// Save is on only when the form has changes. The page asks before the admin leaves with unsaved changes.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SubmitEvent } from "react";

import { api, unwrap } from "@/api/client";
import { settingsQuery } from "@/api/queries";
import type { SecretState, Settings } from "@/api/types";
import { ConfigFile } from "@/components/ConfigFile";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { LeaveGuard } from "@/components/LeaveGuard";
import { QueryPending } from "@/components/QueryPending";
import { Section } from "@/components/Section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { usePageTitle } from "@/lib/pageTitle";

// A `select` field shows the values that the API gives for it (metrics_intervals).
const FIELDS: { key: keyof Settings; label: string; numeric?: boolean; select?: boolean }[] = [
  { key: "check_interval_hours", label: "Check interval (hours)", numeric: true },
  { key: "restart_count", label: "Restart loop: restarts", numeric: true },
  { key: "restart_window_minutes", label: "Restart loop: window (minutes)", numeric: true },
  { key: "ntfy_url", label: "ntfy URL" },
  { key: "ntfy_topic", label: "ntfy topic" },
  { key: "llm_url", label: "LLM URL" },
  { key: "llm_model", label: "LLM model" },
  { key: "public_url", label: "WT URL (for links in notifications)" },
  { key: "metrics_interval_seconds", label: "Metrics interval (seconds)", select: true },
];

// The label of each field, for the field errors of the API.
const LABELS: Record<string, string> = Object.fromEntries(FIELDS.map(({ key, label }) => [key, label]));

// `use`: what WT uses the secret for (static help text).
const SECRETS: { key: keyof SecretState; label: string; use: string }[] = [
  { key: "github_token", label: "GitHub token", use: "Gives a higher GitHub API rate limit for the update checks." },
  { key: "ntfy_token", label: "ntfy token", use: "Lets WT send to an ntfy topic that needs a login." },
  { key: "llm_api_key", label: "LLM API key", use: "Lets WT use the LLM server for the release note summaries." },
];

export function SettingsPage() {
  usePageTitle("Settings");
  const { data, error } = useQuery(settingsQuery);
  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold">Settings</h1>
      {data === undefined ? (
        <QueryPending error={error} />
      ) : (
        <>
          <SettingsForm values={data.values} intervals={data.metrics_intervals} />
          <Secrets secrets={data.secrets} />
        </>
      )}
      <ConfigFile />
    </div>
  );
}

/** The text of each input. No value is an empty text. */
function formValues(values: Settings): Record<string, string> {
  return Object.fromEntries(FIELDS.map(({ key }) => [key, String(values[key] ?? "")]));
}

function SettingsForm({ values, intervals }: { values: Settings; intervals: number[] }) {
  const queryClient = useQueryClient();
  // The saved values, to tell if the form has changes. A save gives the new saved values.
  const [saved, setSaved] = useState(() => formValues(values));
  const [form, setForm] = useState(saved);
  const changed = FIELDS.some(({ key }) => form[key] !== saved[key]);
  // The form sends the text of each input. The backend validates and converts the
  // values (for example "24" to 24, "" to null) and gives an error per field.
  const body = form as unknown as Settings;
  const save = useMutation({
    mutationFn: async () => unwrap(await api.PUT("/api/settings", { body })),
    onSuccess: (result) => {
      queryClient.setQueryData(settingsQuery.queryKey, result);
      // The form shows the values as the backend saved them (for example "024" as "24").
      const next = formValues(result.values);
      setSaved(next);
      setForm(next);
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
      {FIELDS.map(({ key, label, numeric, select }) => {
        const onChange = (event: { target: { value: string } }) => {
          setForm({ ...form, [key]: event.target.value });
          save.reset();
          sendTest.reset();
        };
        return select ? (
          <SelectField key={key} label={label} value={form[key]} options={intervals} onChange={onChange} />
        ) : (
          <Field key={key} label={label} inputMode={numeric ? "numeric" : undefined} value={form[key]} onChange={onChange} />
        );
      })}
      <FormError error={save.error} labels={LABELS} />
      <FormError error={sendTest.error} labels={LABELS} />
      <LeaveGuard when={changed} />
      {/* The buttons stay at the bottom of the window, so that Save is always in view. */}
      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t bg-background/95 px-4 py-3 backdrop-blur">
        <Button type="submit" disabled={!changed || save.isPending}>
          Save
        </Button>
        {changed && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setForm(saved);
              save.reset();
              sendTest.reset();
            }}
          >
            Discard
          </Button>
        )}
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
        {changed && <span className="text-sm font-medium text-warning">Unsaved changes</span>}
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
      <ul className="divide-y rounded-xl border bg-card text-sm shadow-xs">
        {SECRETS.map(({ key, label, use }) => (
          <li key={key} className="space-y-0.5 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{label}</span>
              <Badge variant={secrets[key] === "set" ? "success" : "outline"}>{secrets[key]}</Badge>
            </div>
            <p className="text-muted-foreground">{use}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

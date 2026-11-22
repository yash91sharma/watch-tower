// First setup. Step 1: the setup token from the WT log. Step 2: TOTP, password and code.
// A step list above the form shows the current step.
// After the setup, the backend logs the admin in, and the auth guard opens the app.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState, type SubmitEvent } from "react";

import { authStateQuery } from "@/api/queries";
import { api, unwrap } from "@/api/client";
import type { SetupBegin } from "@/api/types";
import { AuthCard } from "@/components/AuthCard";
import { Field, TotpCodeField } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { isTotpCode, TOTP_CODE_ERROR } from "@/lib/totp";
import { cn } from "@/lib/utils";
import { usePageTitle } from "@/lib/pageTitle";

/** The result of step 1: the token (step 2 sends it again) and the new TOTP key. */
interface Started {
  token: string;
  totp: SetupBegin;
}

export function SetupPage() {
  usePageTitle("Set up");
  const [started, setStarted] = useState<Started | null>(null);
  return (
    <AuthCard title="Set up Watch Tower">
      <Steps current={started === null ? 0 : 1} />
      {started === null ? <TokenStep onStarted={setStarted} /> : <FinishStep {...started} />}
    </AuthCard>
  );
}

function TokenStep({ onStarted }: { onStarted: (started: Started) => void }) {
  const [token, setToken] = useState("");
  const begin = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/auth/setup/begin", { body: { token } })),
    onSuccess: (totp) => {
      onStarted({ token, totp });
    },
  });

  function onSubmit(event: SubmitEvent) {
    event.preventDefault();
    begin.mutate();
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <p className="text-sm text-muted-foreground">
        Get the setup token from the WT log: <code>docker logs wt</code>
      </p>
      <Field
        label="Setup token"
        autoComplete="off"
        required
        value={token}
        onChange={(event) => {
          setToken(event.target.value);
        }}
      />
      <FormError error={begin.error} />
      <Button type="submit" disabled={begin.isPending}>
        Next
      </Button>
    </form>
  );
}

function FinishStep({ token, totp }: Started) {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [code, setCode] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const finish = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/auth/setup/finish", { body: { token, password, totp_code: code } })),
    onSuccess: (state) => {
      queryClient.setQueryData(authStateQuery.queryKey, state);
    },
  });

  function onSubmit(event: SubmitEvent) {
    event.preventDefault();
    const error =
      password !== password2 ? "The two passwords are not the same" : isTotpCode(code) ? null : TOTP_CODE_ERROR;
    setFormError(error);
    if (error === null) finish.mutate();
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      <h2 className="font-medium">Authenticator app</h2>
      <p className="text-sm text-muted-foreground">Add this TOTP key to your authenticator app.</p>
      <img
        className="size-48 bg-white p-2"
        alt="QR code for the authenticator app"
        src={`data:image/svg+xml,${encodeURIComponent(totp.qr_svg)}`}
      />
      <p className="text-sm">
        Secret: <code className="break-all">{totp.totp_secret}</code>
      </p>
      <h2 className="border-t pt-4 font-medium">Password</h2>
      <Field
        label="Password"
        type="password"
        autoComplete="new-password"
        required
        value={password}
        onChange={(event) => {
          setPassword(event.target.value);
        }}
      />
      <Field
        label="Password again"
        type="password"
        autoComplete="new-password"
        required
        value={password2}
        onChange={(event) => {
          setPassword2(event.target.value);
        }}
      />
      <TotpCodeField value={code} onChange={setCode} />
      <FormError error={formError ?? finish.error} />
      <Button type="submit" disabled={finish.isPending}>
        Set up
      </Button>
    </form>
  );
}

const STEPS = ["Setup token", "Authenticator and password"];

/** The setup steps, with the current step marked and the steps before it done. */
function Steps({ current }: { current: number }) {
  return (
    <ol aria-label="Setup steps" className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {STEPS.map((label, index) => (
        <li
          key={label}
          aria-current={index === current ? "step" : undefined}
          className={cn("flex items-center gap-2", index === current ? "font-medium" : "text-muted-foreground")}
        >
          <span
            aria-hidden
            className={cn(
              "flex size-6 items-center justify-center rounded-full border text-xs",
              index === current && "border-primary bg-primary text-primary-foreground",
              index < current && "border-success bg-success-muted text-success",
            )}
          >
            {index < current ? <Check className="size-3.5" /> : index + 1}
          </span>
          {label}
          {index < current && <span className="sr-only"> (done)</span>}
        </li>
      ))}
    </ol>
  );
}

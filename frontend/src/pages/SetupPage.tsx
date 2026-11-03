// First setup. Step 1: the setup token from the WT log. Step 2: TOTP, password and code.
// After the setup, the backend logs the admin in, and the auth guard opens the app.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { authStateQuery } from "@/api/auth";
import { api, unwrap } from "@/api/client";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";

export function SetupPage() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [code, setCode] = useState("");
  const [mismatch, setMismatch] = useState(false);

  const begin = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/auth/setup/begin", { body: { token } })),
  });
  const finish = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/auth/setup/finish", { body: { token, password, totp_code: code } })),
    onSuccess: (state) => {
      queryClient.setQueryData(authStateQuery.queryKey, state);
    },
  });

  function onBegin(event: SubmitEvent) {
    event.preventDefault();
    begin.mutate();
  }

  function onFinish(event: SubmitEvent) {
    event.preventDefault();
    setMismatch(password !== password2);
    if (password === password2) finish.mutate();
  }

  const totp = begin.data;
  return (
    <main className="mx-auto max-w-md space-y-4 px-4 py-8">
      <h1 className="text-xl font-semibold">Set up Watch Tower</h1>
      {totp === undefined ? (
        <form className="space-y-4" onSubmit={onBegin}>
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
      ) : (
        <form className="space-y-4" onSubmit={onFinish}>
          <p className="text-sm text-muted-foreground">Add this TOTP key to your authenticator app.</p>
          <img
            className="size-48 bg-white p-2"
            alt="QR code for the authenticator app"
            src={`data:image/svg+xml,${encodeURIComponent(totp.qr_svg)}`}
          />
          <p className="text-sm">
            Secret: <code className="break-all">{totp.totp_secret}</code>
          </p>
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
          <Field
            label="TOTP code"
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            value={code}
            onChange={(event) => {
              setCode(event.target.value);
            }}
          />
          <FormError error={mismatch ? "The two passwords are not the same" : finish.error} />
          <Button type="submit" disabled={finish.isPending}>
            Set up
          </Button>
        </form>
      )}
    </main>
  );
}

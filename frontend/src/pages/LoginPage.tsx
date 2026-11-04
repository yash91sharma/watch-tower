// Login with the password and a TOTP code. After the login, the auth guard opens the app.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { authStateQuery } from "@/api/auth";
import { api, ApiError, unwrap } from "@/api/client";
import { Field } from "@/components/Field";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { isTotpCode, TOTP_CODE_ERROR } from "@/lib/totp";
import { plural } from "@/lib/utils";

/** The error text. After the login limit (429), the wait time from Retry-After. */
function loginError(error: Error | null): Error | string | null {
  if (error instanceof ApiError && error.status === 429 && error.retryAfter !== null) {
    const minutes = Math.ceil(error.retryAfter / 60);
    return `Too many failed attempts. Try again in ${plural(minutes, "minute", "minutes")}.`;
  }
  return error;
}

export function LoginPage() {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [badCode, setBadCode] = useState(false);

  const login = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/auth/login", { body: { password, totp_code: code } })),
    onSuccess: (state) => {
      queryClient.setQueryData(authStateQuery.queryKey, state);
    },
  });

  function onSubmit(event: SubmitEvent) {
    event.preventDefault();
    const bad = !isTotpCode(code);
    setBadCode(bad);
    if (!bad) login.mutate();
  }

  return (
    <main className="mx-auto max-w-md space-y-4 px-4 py-8">
      <h1 className="text-xl font-semibold">Log in</h1>
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
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
        <FormError error={badCode ? TOTP_CODE_ERROR : loginError(login.error)} />
        <Button type="submit" disabled={login.isPending}>
          Log in
        </Button>
      </form>
    </main>
  );
}

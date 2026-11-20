// A form input with its label, and the TOTP code input of the login and setup forms.
import { useId, type ComponentProps } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function Field({ label, ...props }: { label: string } & ComponentProps<"input">) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} {...props} />
    </div>
  );
}

/** The 6-digit code of the authenticator app. A phone shows the number keyboard. */
export function TotpCodeField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <Field
      label="TOTP code"
      inputMode="numeric"
      autoComplete="one-time-code"
      required
      value={value}
      onChange={(event) => {
        onChange(event.target.value);
      }}
    />
  );
}

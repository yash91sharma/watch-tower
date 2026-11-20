// The error of a form: a text, or an API error with its field errors.
import { ApiError } from "@/api/client";

/**
 * `labels` gives the form label of an API field (for example "check_interval_hours" to
 * "Check interval (hours)"). A field with no label shows its API name.
 */
export function FormError({ error, labels = {} }: { error: Error | string | null; labels?: Record<string, string> }) {
  if (error === null) return null;
  const fields = error instanceof ApiError ? error.fields : [];
  // With field errors, the error text is only the HTTP status ("Unprocessable Content").
  const message = fields.length > 0 ? "Some values are not correct:" : typeof error === "string" ? error : error.message;
  return (
    <div role="alert" className="text-sm text-destructive">
      <p>{message}</p>
      {fields.length > 0 && (
        <ul className="list-disc pl-5">
          {fields.map((item) => (
            <li key={item.field}>
              {labels[item.field] ?? item.field}: {item.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

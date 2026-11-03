// The error of a form: a text, or an API error with its field errors.
import { ApiError } from "@/api/client";

export function FormError({ error }: { error: Error | string | null }) {
  if (error === null) return null;
  const message = typeof error === "string" ? error : error.message;
  const fields = error instanceof ApiError ? error.fields : [];
  return (
    <div role="alert" className="text-sm text-destructive">
      <p>{message}</p>
      {fields.length > 0 && (
        <ul className="list-disc pl-5">
          {fields.map((item) => (
            <li key={item.field}>
              {item.field}: {item.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

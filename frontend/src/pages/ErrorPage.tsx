// The page for an error while a route renders (the router error boundary).
import { Link, useRouteError } from "react-router";

export function ErrorPage() {
  const error = useRouteError();
  const message = error instanceof Error ? error.message : "Unknown error";
  return (
    <main className="mx-auto max-w-md space-y-2 px-4 py-8">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="text-muted-foreground">{message}</p>
      <Link className="underline" to="/">
        Open the container list
      </Link>
    </main>
  );
}

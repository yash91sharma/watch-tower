import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link className="underline" to="/">
        Open the container list
      </Link>
    </div>
  );
}

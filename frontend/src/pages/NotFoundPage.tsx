import { Link } from "react-router";

import { usePageTitle } from "@/lib/pageTitle";

export function NotFoundPage() {
  usePageTitle("Page not found");
  return (
    <div className="space-y-2">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link className="underline" to="/">
        Open the home page
      </Link>
    </div>
  );
}

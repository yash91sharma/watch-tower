// Sample test: makes sure that jsdom, Testing Library and MSW work together.
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { useEffect, useState } from "react";
import { expect, test } from "vitest";

import { server } from "@/test/server";

function Status() {
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    void fetch(new URL("/api/sample", location.origin))
      .then((res) => res.json() as Promise<{ status: string }>)
      .then((body) => {
        setStatus(body.status);
      });
  }, []);
  return <p>Status: {status}</p>;
}

test("a component gets data from an MSW handler", async () => {
  server.use(http.get("/api/sample", () => HttpResponse.json({ status: "ok" })));

  render(<Status />);

  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
});

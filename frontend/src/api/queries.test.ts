import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";

import { containerHistoryQuery, overviewQuery, sparklinesQuery, vmHistoryQuery } from "@/api/queries";
import { history } from "@/test/fixtures";
import { server } from "@/test/server";

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

test("the metric queries get the overview and the sparklines", async () => {
  const queryClient = client();

  expect((await queryClient.query(overviewQuery)).counts.apps_label).toBe("1 app");
  expect((await queryClient.query(sparklinesQuery)).containers.web?.cpu).toHaveLength(60);
});

test("the history queries send the range and the container name", async () => {
  const urls: string[] = [];
  server.use(
    http.get("*/api/metrics/*", ({ request }) => {
      urls.push(new URL(request.url).pathname + new URL(request.url).search);
      return HttpResponse.json(history());
    }),
  );
  const queryClient = client();

  await queryClient.query(vmHistoryQuery("7d"));
  await queryClient.query(containerHistoryQuery("web", "30d"));

  expect(urls).toEqual(["/api/metrics/vm/history?range=7d", "/api/metrics/containers/web/history?range=30d"]);
});

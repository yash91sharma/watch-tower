// All routes. The app shell (Layout) wraps the pages that need a login.
import type { RouteObject } from "react-router";

import { Layout } from "@/components/Layout";
import { ContainerPage } from "@/pages/ContainerPage";
import { ContainersPage } from "@/pages/ContainersPage";
import { ErrorPage } from "@/pages/ErrorPage";
import { LoginPage } from "@/pages/LoginPage";
import { LogsPage } from "@/pages/LogsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SetupPage } from "@/pages/SetupPage";

export const routes: RouteObject[] = [
  { path: "/setup", element: <SetupPage />, errorElement: <ErrorPage /> },
  { path: "/login", element: <LoginPage />, errorElement: <ErrorPage /> },
  {
    element: <Layout />,
    errorElement: <ErrorPage />,
    children: [
      { path: "/", element: <ContainersPage /> },
      { path: "/containers/:name", element: <ContainerPage /> },
      { path: "/containers/:name/logs", element: <LogsPage /> },
      { path: "/settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

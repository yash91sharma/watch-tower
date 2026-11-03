// All routes. The app shell (Layout) wraps the pages that need a login.
// The auth guard opens the page that matches the auth state.
import type { RouteObject } from "react-router";

import { AuthGuard } from "@/components/AuthGuard";
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
  {
    path: "/setup",
    element: (
      <AuthGuard area="setup">
        <SetupPage />
      </AuthGuard>
    ),
    errorElement: <ErrorPage />,
  },
  {
    path: "/login",
    element: (
      <AuthGuard area="login">
        <LoginPage />
      </AuthGuard>
    ),
    errorElement: <ErrorPage />,
  },
  {
    element: (
      <AuthGuard area="app">
        <Layout />
      </AuthGuard>
    ),
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

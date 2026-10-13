import { createRoot } from "react-dom/client";

import * as Sentry from "@sentry/react";

import App from "@/App";
import ErrorFallback from "@/components/ErrorFallback";
import "@/i18n";
import "@/index.css";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    // Tunnel envelopes through our own backend so ad-blockers and
    // restrictive CSPs don't silently drop error reports.
    tunnel: "/api/sentry-tunnel",
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_RELEASE,
    tracesSampleRate: 0.0,
    // No `dataCollection` on purpose: left unset, Sentry keeps the legacy
    // no-PII behaviour (no user info or bodies; PII headers/cookies/query
    // params filtered). Setting it at all — even one field — switches every
    // unset field to permissive defaults, so spell out all fields if added.
  });
}

document.documentElement.lang = "he";
document.documentElement.dir = "rtl";

createRoot(document.getElementById("root")!).render(
  <Sentry.ErrorBoundary fallback={<ErrorFallback />}>
    <App />
  </Sentry.ErrorBoundary>,
);

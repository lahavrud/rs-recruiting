import { type ReactNode } from "react";

import * as Sentry from "@sentry/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Button from "@/components/ui/Button";

interface Props {
  children: ReactNode;
}

function RouteErrorFallback({ resetError }: { resetError: () => void }) {
  const { t } = useTranslation(["common", "ui"]);
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-16 text-center">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("common:errorEyebrow")}
      </p>
      <p className="mt-4 max-w-sm text-sm text-white/50">
        {t("common:errors.routeCrashed")}
      </p>
      <div className="mt-6 flex items-center gap-3">
        <Button variant="primary" size="sm" onClick={resetError}>
          {t("common:retry")}
        </Button>
        <Link
          to="/dashboard"
          className="text-sm text-white/45 underline-offset-4 transition hover:text-white/70 hover:underline"
        >
          {t("ui:notFound.goToDashboard")}
        </Link>
      </div>
    </div>
  );
}

/** Scoped error boundary for a single route's page content. Leaves the
 *  AppShell (header/sidebar) intact on a render crash instead of dropping
 *  to the global full-screen fallback in main.tsx. */
export default function RouteErrorBoundary({ children }: Props) {
  return (
    <Sentry.ErrorBoundary
      fallback={({ resetError }) => <RouteErrorFallback resetError={resetError} />}
    >
      {children}
    </Sentry.ErrorBoundary>
  );
}

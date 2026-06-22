import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";

interface NoResultsProps {
  /** Override the default `publicJobs:board.noResults` message. */
  message?: string;
  /** Optional CTA rendered below the message (e.g. "clear filters"). */
  children?: ReactNode;
}

/**
 * Dashed-border placeholder shown when a filter or search produces an empty
 * result inside an otherwise non-empty list. For "no items at all" use
 * `EmptyState` instead.
 */
export default function NoResults({ message, children }: NoResultsProps) {
  const { t } = useTranslation('publicJobs');
  return (
    <div className="rounded-xl border border-dashed border-white/10 py-16 text-center">
      <p className="text-sm text-white/40">
        {message ?? t("publicJobs:board.noResults")}
      </p>
      {children}
    </div>
  );
}

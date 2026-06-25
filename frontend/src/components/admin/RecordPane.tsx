import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";

interface RecordPaneProps<T> {
  id: number | null;
  /** Pre-loaded entity (e.g. already in the rail's page of results) — skips the fetch. */
  entity?: T;
  fetcher: (id: number, signal: AbortSignal) => Promise<T>;
  listPath: string;
  listLabel: string;
  crumbLabel: (entity: T) => ReactNode;
  emptyHeadline: string;
  emptyDescription?: string;
  notFoundHeadline: string;
  loadErrorMessage: string;
  children: (entity: T) => ReactNode;
}

/**
 * Right-hand record pane shell shared by every admin record-as-page workspace:
 * fetch-by-id (skipped when `entity` is already known), not-found/load-error/skeleton
 * states, and the breadcrumb header (mobile back-link + desktop breadcrumb nav).
 */
export default function RecordPane<T>({
  id,
  entity,
  fetcher,
  listPath,
  listLabel,
  crumbLabel,
  emptyHeadline,
  emptyDescription,
  notFoundHeadline,
  loadErrorMessage,
  children,
}: RecordPaneProps<T>) {
  const { t } = useTranslation("common");
  const navigate = useNavigate();
  const [fetched, setFetched] = useState<T | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setFetched(null);
    setNotFound(false);
    setLoadError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    if (id == null || entity) return;
    const ctrl = new AbortController();
    fetcher(id, ctrl.signal)
      .then(setFetched)
      .catch((e) => {
        if (axios.isCancel(e)) return;
        if (axios.isAxiosError(e) && e.response?.status === 404) {
          setNotFound(true);
        } else {
          setLoadError(true);
        }
      });
    return () => ctrl.abort();
  }, [id, entity, fetcher]);

  if (id == null) {
    return (
      <EmptyState eyebrow={listLabel} headline={emptyHeadline} description={emptyDescription} />
    );
  }

  const value = entity ?? fetched;

  if (!value) {
    if (notFound) {
      return <EmptyState eyebrow={listLabel} headline={notFoundHeadline} />;
    }
    if (loadError) {
      return <ErrorState message={loadErrorMessage} />;
    }
    return (
      <div className="animate-pulse rounded-xl border border-white/8 bg-card p-4 sm:p-6">
        <div className="mb-4 h-3 w-32 rounded bg-white/5" />
        <div className="h-5 w-48 rounded bg-white/8" />
        <div className="mt-3 h-3 w-64 rounded bg-white/5" />
      </div>
    );
  }

  // Prefer real browser-back so we return to wherever the admin actually came
  // from (e.g. a relation link from another record) instead of always the list.
  // history.state.idx > 0 means the previous entry was created by this app's
  // router, so going back stays in-app rather than leaving it.
  function handleBack() {
    const idx = (window.history.state as { idx?: number } | null)?.idx;
    if (typeof idx === "number" && idx > 0) {
      navigate(-1);
    } else {
      navigate(listPath);
    }
  }

  return (
    <div className="@container rounded-xl border border-white/8 bg-card p-4 sm:p-6">
      <button
        type="button"
        onClick={handleBack}
        className="mb-4 flex items-center gap-1.5 text-sm text-white/50 transition hover:text-copper md:hidden"
      >
        <BackChevron />
        {t("common:back")}
      </button>

      <nav className="mb-4 hidden items-center gap-2 text-sm text-white/50 md:flex">
        <Link to={listPath} className="transition hover:text-copper">
          {listLabel}
        </Link>
        <span aria-hidden>›</span>
        <span className="text-white/80">{crumbLabel(value)}</span>
      </nav>

      {children(value)}
    </div>
  );
}

function BackChevron() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-3.5"
      aria-hidden="true"
    >
      <path d="M6 4 L10 8 L6 12" />
    </svg>
  );
}

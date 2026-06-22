import { useEffect, useRef, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import CompanyName from "@/components/ui/CompanyName";
import PageHeader from "@/components/ui/PageHeader";
import { useFetch } from "@/hooks/useFetch";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import {
  listMyApplications,
  type CandidateApplicationListItem,
  type CandidateApplicationsPage as ApplicationsPageResult,
} from "@/services/candidate";

const BANNER_DISMISS_MS = 4000;

export default function CandidateApplicationsPage() {
  const { t, i18n } = useTranslation('candidate');
  const location = useLocation();
  const navigate = useNavigate();
  const [items, setItems] = useState<CandidateApplicationListItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [withdrawnBanner, setWithdrawnBanner] = useState(
    () => !!(location.state as Record<string, unknown> | null)?.withdrawn,
  );
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (withdrawnBanner) {
      navigate(".", { replace: true, state: {} });
      bannerTimerRef.current = setTimeout(() => setWithdrawnBanner(false), BANNER_DISMISS_MS);
    }
    return () => {
      if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const { data: firstPage, loading, error: fetchError } = useFetch<ApplicationsPageResult>(
    listMyApplications,
    [],
  );
  useResetOnTrigger(firstPage, () => {
    setItems(firstPage!.items);
    setCursor(firstPage!.next_cursor);
  });
  useResetOnTrigger(fetchError, () =>
    setError(t("candidate:applications.errors.loadFailed")),
  );

  async function loadMore() {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await listMyApplications(cursor);
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor);
    } catch {
      setError(t("candidate:applications.errors.loadFailed"));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <PageHeader
        eyebrow={t("candidate:applications.eyebrow")}
        subtitle={t("candidate:applications.subtitle")}
      />

      {withdrawnBanner && (
        <div className="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
          {t("candidate:applications.withdraw.withdrawn")}
        </div>
      )}

      {loading && (
        <p className="mt-6 text-white/60">{t("candidate:applications.loading")}</p>
      )}

      {error && !loading && (
        <p className="mt-6 text-danger">{error}</p>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="mt-8 rounded-xl border border-white/8 bg-card p-8 text-center">
          <p className="text-white/70">
            {t("candidate:applications.empty")}
          </p>
          <Link
            to="/jobs"
            className="mt-4 inline-block rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
          >
            {t("candidate:applications.browseLink")}
          </Link>
        </div>
      )}

      {!loading && items.length > 0 && (
        <ul className="mt-8 space-y-3">
          {items.map((row) => (
            <li key={row.id}>
              <Link
                to={`/candidate/applications/${row.id}`}
                className="block rounded-xl border border-white/8 bg-card p-5 transition-colors hover:border-white/20 hover:bg-card-raised"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <CompanyName name={row.company.name} className="truncate" />
                  <span className="shrink-0 text-xs text-white/50">
                    {formatRelative(row.submitted_at, i18n.language, t)}
                  </span>
                </div>
                <p className="mt-2 text-base text-white/85">{row.job.title}</p>
                {row.job.closed && (
                  <span className="mt-3 inline-block rounded-sm border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-widest text-white/50">
                    {t("candidate:applications.closedPill")}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}

      {!loading && cursor && (
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/70 hover:border-white/40 hover:text-white/90 disabled:opacity-50"
          >
            {loadingMore
              ? t("candidate:applications.loading")
              : t("candidate:applications.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Quick relative-time formatter for a small handful of buckets. Avoids
 * pulling in date-fns/Intl.RelativeTimeFormat for what is currently just
 * the applications list — keeps the page chunk small.
 */
function formatRelative(
  iso: string,
  _locale: string,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const submitted = new Date(iso).getTime();
  const now = Date.now();
  const days = Math.max(0, Math.floor((now - submitted) / 86_400_000));
  if (days === 0) return t("candidate:applications.relative.today");
  if (days === 1) return t("candidate:applications.relative.yesterday");
  if (days < 7) return t("candidate:applications.relative.daysAgo", { count: days });
  if (days < 30)
    return t("candidate:applications.relative.weeksAgo", {
      count: Math.floor(days / 7),
    });
  if (days < 365)
    return t("candidate:applications.relative.monthsAgo", {
      count: Math.floor(days / 30),
    });
  return t("candidate:applications.relative.yearsAgo", {
    count: Math.floor(days / 365),
  });
}

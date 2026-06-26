import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { CollapsibleSection } from "@/components/admin/AnimatedAccordion";
import { MatchList, type MatchEntry } from "@/components/admin/MatchList";
import Eyebrow from "@/components/ui/Eyebrow";
import StatusBadge from "@/components/ui/StatusBadge";
import { getApplications } from "@/services/adminApplications";
import { getJobCandidateMatches } from "@/services/adminJobs";
import type { JobCandidateMatchRead } from "@/types/candidates";
import type { JobRead } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

/**
 * Tiny diagonal sash anchored to the top-right corner of a desktop title
 * cell. Sits z-above the text so the title doesn't push it out, and small
 * enough that it doesn't visually overlap the title.
 */
export function FeaturedDesktopSash() {
  const { t } = useTranslation(["admin", "common", "http", "publicJobs"]);
  return (
    <span
      className="pointer-events-none absolute right-0 top-0 z-20 h-7 w-7 overflow-hidden"
      aria-label={t("publicJobs:board.featured")}
    >
      <span className="absolute top-1 -right-3 inline-flex w-12 origin-center rotate-45 items-center justify-center bg-gradient-to-r from-copper via-gold to-gold-light py-px text-white shadow-[0_1px_2px_rgba(0,0,0,0.5)]">
        <svg
          viewBox="0 0 24 24"
          fill="currentColor"
          className="size-2.5"
          aria-hidden="true"
        >
          <path d="M12 2.5l3.09 6.26 6.91 1.01-5 4.87 1.18 6.88L12 18.27l-6.18 3.25L7 14.64 2 9.77l6.91-1.01L12 2.5z" />
        </svg>
      </span>
    </span>
  );
}

export function JobDetailBody({
  job,
  statusLabels,
  statusColors,
  companyName,
  onLeavePage,
}: {
  job: JobRead;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  companyName?: string;
  onLeavePage?: () => void;
}) {
  const { t } = useTranslation(["admin", "common", "http", "publicJobs"]);
  const navigate = useNavigate();

  // Lazy-fetch application count for this job. `null` = loading, number = total.
  // We fetch a generous first page; if it's smaller than the limit it's exact.
  // If we got exactly the limit, we report "N+" since there may be more.
  const APP_FETCH_LIMIT = 100;
  const [applicationCount, setApplicationCount] = useState<{
    n: number;
    isCapped: boolean;
  } | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getApplications({ job_id: job.id, limit: APP_FETCH_LIMIT }, ctrl.signal)
      .then((page) =>
        setApplicationCount({
          n: page.items.length,
          isCapped: page.items.length === APP_FETCH_LIMIT,
        }),
      )
      .catch(() => {});
    return () => ctrl.abort();
  }, [job.id]);

  const [matches, setMatches] = useState<JobCandidateMatchRead[] | null>(null);
  const [hasMatchesError, setHasMatchesError] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setMatches(null);
    setHasMatchesError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getJobCandidateMatches(job.id, ctrl.signal)
      .then(setMatches)
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setHasMatchesError(true);
      });
    return () => ctrl.abort();
  }, [job.id]);
  const matchEntries: MatchEntry[] | null =
    matches?.map((m) => ({
      key: m.candidate.id,
      name: m.candidate.full_name,
      meta: m.candidate.email,
      score: m.score,
      onClick: () => {
        onLeavePage?.();
        navigate(`/admin/candidates/${m.candidate.id}`);
      },
    })) ?? null;

  const salaryStr =
    job.salary_min != null && job.salary_max != null
      ? `${job.salary_min.toLocaleString("he-IL")}–${job.salary_max.toLocaleString("he-IL")} ₪/חודש`
      : null;

  return (
    <div className="space-y-4 text-sm">
      {/* Header strip: status + featured ribbon eyebrow only */}
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge
          label={statusLabels[job.status]}
          colorCls={statusColors[job.status]}
        />
        {job.is_featured && (
          <span className="inline-flex items-center gap-1 rounded-full border border-gold/40 bg-gold/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-gold">
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="size-2.5"
              aria-hidden="true"
            >
              <path d="M12 2c.7 2.5 2.5 3.5 2.5 6a2.5 2.5 0 0 1-5 0c0-1 .4-1.7 1-2.3C9 7 9 5 12 2zm0 8c3.5 0 6 2.8 6 6.3a6 6 0 1 1-12 0c0-2 1-3.5 2.4-4.5-.1 1.6.7 2.7 1.9 3.3-.7-2.2.7-3.5 1.7-5.1z" />
            </svg>
            {t("publicJobs:board.featured")}
          </span>
        )}
      </div>

      {/* Metadata grid — labeled fields read cleanly on mobile */}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs sm:grid-cols-[auto_1fr_auto_1fr] sm:gap-x-6">
        <dt className="text-white/40">{t("admin:jobs.fields.company")}</dt>
        <dd>
          <button
            type="button"
            onClick={() => {
              onLeavePage?.();
              navigate(`/admin/companies/${job.company_id}`);
            }}
            className="inline-flex items-center rounded-sm border border-white/10 bg-white/5 px-2 py-0.5 text-copper/90 transition hover:border-copper/30 hover:bg-copper/10 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 sm:text-copper/85 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline"
          >
            {companyName ?? t("admin:jobs.companyLabel", { id: job.company_id })}
          </button>
        </dd>
        <dt className="text-white/40">{t("admin:jobs.submittedLabel")}</dt>
        <dd className="text-white/70">{formatDate(job.created_at)}</dd>
        {salaryStr && (
          <>
            <dt className="text-white/40">{t("common:salary")}</dt>
            <dd className="font-medium text-copper/85">{salaryStr}</dd>
          </>
        )}
        <dt className="text-white/40">{t("admin:jobs.candidatesLabel")}</dt>
        <dd className="inline-flex items-center gap-1.5">
          <span className="font-medium text-copper/85">
            {applicationCount == null
              ? "…"
              : applicationCount.isCapped
                ? `${applicationCount.n}+`
                : applicationCount.n}
          </span>
          {applicationCount != null && applicationCount.n > 0 && (
            <button
              type="button"
              onClick={() => {
                onLeavePage?.();
                navigate(`/admin/applications?job=${job.id}`);
              }}
              className="inline-flex items-center rounded-sm border border-white/10 bg-white/5 px-2 py-0.5 text-white/65 transition hover:border-copper/30 hover:bg-copper/10 hover:text-copper sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 sm:text-white/40 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline"
            >
              {t("admin:jobs.candidatesView")}
            </button>
          )}
        </dd>
      </dl>

      {job.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {job.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-copper/25 bg-copper/10 px-2.5 py-0.5 text-xs font-medium text-copper/90"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Short description: lifted into a subtle well so it doesn't compete with the metadata */}
      <div className="rounded-md border border-white/6 bg-well/30 px-3 py-2.5">
        <Eyebrow>{t("admin:jobs.fields.shortDescription")}</Eyebrow>
        <p className="mt-1 leading-relaxed text-white/80">{job.short_description}</p>
      </div>

      <CollapsibleSection title={t("admin:jobs.fields.description")}>
        <p className="whitespace-pre-wrap leading-relaxed text-white/75">
          {job.description}
        </p>
      </CollapsibleSection>
      {job.requirements.length > 0 && (
        <CollapsibleSection title={t("admin:jobs.fields.requirements")}>
          <ul className="space-y-1.5 text-white/75">
            {job.requirements.map((req, i) => (
              <li key={i} className="flex items-start gap-2">
                <span
                  aria-hidden="true"
                  className="mt-2 inline-block size-1.5 shrink-0 rounded-full bg-copper/70"
                />
                <span>{req.text}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}
      <CollapsibleSection title={t("admin:jobs.matchesSection")}>
        <MatchList
          entries={matchEntries}
          hasError={hasMatchesError}
          emptyMessage={t("admin:jobs.noMatches")}
          errorMessage={t("admin:jobs.matchesLoadError")}
        />
      </CollapsibleSection>
    </div>
  );
}

/**
 * Mobile card with controlled expand/collapse. A dedicated chevron column at
 * the inline-start of the summary row makes the affordance unmissable, the
 * border tints copper when open, and a "סגור" button anchors the bottom of
 * the expanded content so the user can always close without scrolling back up.
 *
 * The expand/collapse uses the grid-template-rows 0fr→1fr trick so the height
 * animates smoothly without us having to measure the content.
 */
export function MobileJobCard({
  job,
  statusLabels,
  statusColors,
  companyName,
  actions,
}: {
  job: JobRead;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  companyName?: string;
  actions: React.ReactNode;
}) {
  const { t } = useTranslation(["admin", "common", "http", "publicJobs"]);
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div
      className={`relative overflow-hidden rounded-xl border bg-card transition-colors duration-200 ${
        isOpen
          ? "border-copper/40 bg-card-raised"
          : "border-white/8 hover:border-white/15"
      }`}
    >
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        aria-expanded={isOpen}
        aria-label={isOpen ? t("admin:jobs.collapseLabel") : t("admin:jobs.expandLabel")}
        className="flex w-full cursor-pointer items-center gap-3 px-3 py-3 pe-12 text-start active:scale-[0.99]"
      >
        <span
          className={`inline-flex size-7 shrink-0 items-center justify-center rounded-full border transition-colors duration-200 ${
            job.is_featured
              ? isOpen
                ? "border-gold bg-gold/25 text-gold"
                : "border-gold/50 bg-gold/10 text-gold"
              : isOpen
                ? "border-copper bg-copper/15 text-copper"
                : "border-white/15 text-white/45"
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className={`size-3.5 transition-transform duration-300 ease-out ${isOpen ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M4.22 5.72a.75.75 0 0 1 1.06 0L8 8.44l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 6.78a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </span>
        <p className="min-w-0 flex-1 truncate font-medium text-white/85">{job.title}</p>
        <StatusBadge
          label={statusLabels[job.status]}
          colorCls={statusColors[job.status]}
        />
      </button>
      <div className="absolute end-1 top-2">{actions}</div>
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`border-t border-white/8 px-4 py-4 transition-opacity duration-200 ${
              isOpen ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            <JobDetailBody
              job={job}
              statusLabels={statusLabels}
              statusColors={statusColors}
              companyName={companyName}
            />
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2 text-xs font-medium text-white/65 transition-colors hover:border-copper/50 hover:text-copper active:scale-[0.99]"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                className="size-3.5"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M11.78 10.28a.75.75 0 0 1-1.06 0L8 7.56l-2.72 2.72a.75.75 0 1 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06Z"
                  clipRule="evenodd"
                />
              </svg>
              {t("admin:jobs.collapseLabel")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

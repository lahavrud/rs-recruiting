import { useEffect } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import SeoHead, { SITE_URL, SITE_NAME } from "@/components/ui/SeoHead";
import { useFetch } from "@/hooks/useFetch";
import { getPublicJob } from "@/services/jobs";
import { errorAlertClsLg } from "@/styles/forms";
import type { JobPublicRead } from "@/types/api";
import { trackEvent } from "@/utils/analytics";
import { formatDateLong as formatDate } from "@/utils/formatDate";
import { formatSalary } from "@/utils/salary";

const JOB_POSTING_VALID_DAYS = 90;

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function buildDescriptionHtml(job: JobPublicRead): string {
  const paragraphs = job.description
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${escapeHtml(p)}</p>`);
  const items = job.requirements
    .map((r) => r.text)
    .filter(Boolean)
    .map((t) => `<li>${escapeHtml(t)}</li>`);
  const reqList = items.length ? `<ul>${items.join("")}</ul>` : "";
  return paragraphs.join("") + reqList;
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-4xl animate-pulse pb-24 lg:pb-0">
      {/* Back link */}
      <div className="mb-6 h-4 w-24 rounded bg-white/8 sm:mb-8" />
      <div className="lg:grid lg:grid-cols-[1fr_280px] lg:items-start lg:gap-8">
        {/* Article */}
        <div className="rounded-xl border border-white/8 bg-card p-5 sm:p-10">
          {/* Header: title + location (left) / status badge (right) */}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-2.5">
              <div className="h-6 w-2/3 rounded bg-white/10 sm:h-7" />
              <div className="h-4 w-1/3 rounded bg-white/6" />
            </div>
            <div className="h-6 w-16 shrink-0 rounded-full bg-white/6" />
          </div>
          {/* Tag chips */}
          <div className="mt-4 flex flex-wrap gap-1.5">
            <div className="h-6 w-20 rounded-full bg-white/6" />
            <div className="h-6 w-24 rounded-full bg-white/6" />
            <div className="h-6 w-16 rounded-full bg-white/6" />
          </div>
          {/* Posted + salary row */}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <div className="h-3 w-28 rounded bg-white/5" />
            <div className="h-4 w-36 rounded bg-white/6" />
          </div>

          <div className="my-6 h-px bg-white/8 sm:my-8" />

          {/* About the role */}
          <div>
            <div className="mb-3 h-3 w-20 rounded bg-white/6" />
            <div className="space-y-2">
              {[1, 0.9, 0.85, 0.7, 0.8].map((w, i) => (
                <div key={i} className="h-3 rounded bg-white/5" style={{ width: `${w * 100}%` }} />
              ))}
            </div>
          </div>

          {/* Requirements — bullet list */}
          <div className="mt-8">
            <div className="mb-3 h-3 w-20 rounded bg-white/6" />
            <ul className="space-y-2">
              {[0.85, 0.7, 0.78, 0.6].map((w, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="inline-block size-1.5 shrink-0 rounded-full bg-white/15" />
                  <div className="h-3 rounded bg-white/5" style={{ width: `${w * 100}%` }} />
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Desktop sidebar — hidden on mobile (replaced by fixed bottom bar) */}
        <aside className="mt-0 hidden lg:sticky lg:top-6 lg:block">
          <div className="rounded-xl border border-white/8 bg-card p-6">
            <div className="h-5 w-3/4 rounded bg-white/10" />
            <div className="mt-2 h-3 w-1/2 rounded bg-white/6" />
            <div className="mt-2 h-3 w-2/5 rounded bg-white/5" />
            <div className="mt-2 h-4 w-3/5 rounded bg-white/6" />
            <div className="mt-5 h-px bg-white/8" />
            <div className="mt-5 h-11 rounded-sm bg-white/6" />
          </div>
        </aside>
      </div>

      {/* Fixed mobile apply bar (lg:hidden) — matches real layout */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-void/95 px-4 py-3 backdrop-blur-md lg:hidden">
        <div className="mx-auto flex max-w-4xl items-center gap-3">
          <div className="h-4 w-28 rounded bg-white/8" />
          <div className="h-11 flex-1 rounded-sm bg-white/8" />
        </div>
      </div>
    </div>
  );
}

function LocationIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="size-3.5 shrink-0"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M8 1.5A4.5 4.5 0 0 0 3.5 6c0 2.625 3.375 7.5 4.5 7.5S12.5 8.625 12.5 6A4.5 4.5 0 0 0 8 1.5ZM8 7.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export default function JobDetailPage() {
  const { t } = useTranslation(['common', 'http', 'https', 'lg', 'publicJobs']);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  // Preserve filter params (q, loc, smin, smax) carried in from the board so
  // the back link returns the user to their filtered list.
  const backTo = { pathname: "/jobs", search: location.search };
  const jobId = id ? Number.parseInt(id, 10) : NaN;
  const validId = Number.isFinite(jobId);

  useEffect(() => {
    if (!validId) navigate("/jobs", { replace: true });
  }, [validId, navigate]);

  const { data: job, loading, error: fetchError } = useFetch<JobPublicRead | null>(async () => {
    if (!validId) return null;
    return getPublicJob(jobId);
  }, [jobId, validId]);

  const error = fetchError
    ? axios.isAxiosError(fetchError) && fetchError.response?.status === 404
      ? t("publicJobs:detail.unavailable")
      : t("publicJobs:detail.errorLoad")
    : null;

  useEffect(() => {
    if (!job) return;
    trackEvent("job_view", { job_id: job.id, job_title: job.title });
  }, [job]);

  if (loading) return <DetailSkeleton />;

  if (error || !job) {
    return (
      <div className="text-center">
        <div className={errorAlertClsLg}>
          {error ?? t("publicJobs:detail.notFound")}
        </div>
        <Link
          to={backTo}
          className="mt-6 inline-block text-sm text-white/40 transition hover:text-copper"
        >
          {t("publicJobs:detail.backToJobs")}
        </Link>
      </div>
    );
  }

  // Sprint 11 / #606 — authed candidate sessions see contextual buttons:
  // * editable → "edit your application" → /candidate/applications/:id
  // * locked   → "you already applied" (disabled)
  // * none     → standard "apply now"
  const myApp = job.my_application;
  const applyHref =
    myApp && myApp.editable
      ? `/candidate/applications/${myApp.id}`
      : `/jobs/${job.id}/apply`;
  const applyLabelKey = myApp
    ? myApp.editable
      ? "publicJobs:detail.editYourApplication"
      : "publicJobs:detail.alreadyApplied"
    : "publicJobs:detail.applyNow";
  const applyDisabled = Boolean(myApp && !myApp.editable);
  const salaryStr = formatSalary(job.salary_min, job.salary_max);

  const validThrough = new Date(
    new Date(job.created_at).getTime() + JOB_POSTING_VALID_DAYS * 86_400_000,
  ).toISOString();

  const jobPosting = {
    "@type": "JobPosting",
    title: job.title,
    description: buildDescriptionHtml(job),
    datePosted: job.created_at,
    validThrough,
    employmentType: "FULL_TIME",
    directApply: true,
    identifier: {
      "@type": "PropertyValue",
      name: SITE_NAME,
      value: String(job.id),
    },
    url: `${SITE_URL}/jobs/${job.id}`,
    hiringOrganization: { "@type": "Organization", name: SITE_NAME, sameAs: SITE_URL },
    jobLocation: {
      "@type": "Place",
      address: { "@type": "PostalAddress", addressLocality: job.location, addressCountry: "IL" },
    },
    ...(job.salary_min != null && job.salary_max != null ? {
      baseSalary: {
        "@type": "MonetaryAmount",
        currency: "ILS",
        value: { "@type": "QuantitativeValue", minValue: job.salary_min, maxValue: job.salary_max, unitText: "MONTH" },
      },
    } : {}),
  };

  const breadcrumb = {
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
      { "@type": "ListItem", position: 2, name: t("publicJobs:board.title"), item: `${SITE_URL}/jobs` },
      { "@type": "ListItem", position: 3, name: job.title, item: `${SITE_URL}/jobs/${job.id}` },
    ],
  };

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [jobPosting, breadcrumb],
  };

  return (
    // pb-24 leaves room for the mobile fixed apply bar; cleared on lg.
    <div className="mx-auto max-w-4xl px-6 pt-24 pb-24 lg:pb-0">
      <SeoHead
        title={job.title}
        description={job.short_description || job.description.slice(0, 160)}
        canonical={`${SITE_URL}/jobs/${job.id}`}
        ogType="article"
        structuredData={structuredData}
      />
      <Link
        to={backTo}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-white/35 transition hover:text-copper sm:mb-8"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-4"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06L7.28 11.78a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
        {t("publicJobs:detail.backToJobs")}
      </Link>

      <div className="lg:grid lg:grid-cols-[1fr_280px] lg:items-start lg:gap-8">
        {/* ── Main article ── */}
        <article
          className={[
            "overflow-hidden rounded-xl border bg-card p-5 sm:p-10",
            job.is_featured ? "border-gold/40" : "border-white/8",
          ].join(" ")}
        >
          {job.is_featured && (
            <p className="mb-3 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-gold">
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                className="size-2.5"
                aria-hidden="true"
              >
                <path d="M12 2c.7 2.5 2.5 3.5 2.5 6a2.5 2.5 0 0 1-5 0c0-1 .4-1.7 1-2.3C9 7 9 5 12 2zm0 8c3.5 0 6 2.8 6 6.3a6 6 0 1 1-12 0c0-2 1-3.5 2.4-4.5-.1 1.6.7 2.7 1.9 3.3-.7-2.2.7-3.5 1.7-5.1z" />
              </svg>
              {t("publicJobs:board.featured")}
            </p>
          )}
          {/* Header: title, status badge, location, posted, salary */}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-semibold leading-tight text-white/95 sm:text-2xl">
                {job.title}
              </h1>
              <p className="mt-2 flex items-center gap-1.5 text-sm text-white/45">
                <LocationIcon />
                {job.location}
              </p>
            </div>

          </div>
          {job.tags.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
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
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <p className="text-xs text-white/30">
              {t("publicJobs:detail.posted")} {formatDate(job.created_at)}
            </p>
            <p className="flex items-center gap-1.5 text-sm">
              <span className="text-white/40">{t("common:salary")}:</span>
              <span className="font-medium text-copper/85">
                {salaryStr ?? t("common:salaryNotSpecified")}
              </span>
            </p>
          </div>

          <div className="my-6 h-px bg-white/8 sm:my-8" />

          {/* About the role */}
          <div>
            <Eyebrow className="mb-3">
              {t("publicJobs:detail.aboutRole")}
            </Eyebrow>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/65 sm:text-[15px]">
              {job.description}
            </p>
          </div>

          {/* Requirements */}
          {job.requirements.length > 0 && (
            <div className="mt-8">
              <Eyebrow className="mb-3">
                {t("publicJobs:detail.requirements")}
              </Eyebrow>
              <ul className="space-y-2 text-sm leading-relaxed text-white/65 sm:text-[15px]">
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
            </div>
          )}
        </article>

        {/* ── Sticky desktop sidebar (hidden on mobile — replaced by fixed bottom bar) ── */}
        <aside className="hidden lg:sticky lg:top-6 lg:mt-0 lg:block">
          <div className="rounded-xl border border-white/8 bg-card p-6">
            <h2 className="font-medium text-white/90">{job.title}</h2>
            <p className="mt-1.5 flex items-center gap-1.5 text-sm text-white/45">
              <LocationIcon />
              {job.location}
            </p>
            <p className="mt-1 text-xs text-white/25">
              {t("publicJobs:detail.posted")} {formatDate(job.created_at)}
            </p>
            <p className="mt-2 flex items-center gap-1.5 text-sm">
              <span className="text-white/40">{t("common:salary")}:</span>
              <span className="font-medium text-copper/85">
                {salaryStr ?? t("common:salaryNotSpecified")}
              </span>
            </p>

            <div className="mt-5 h-px bg-white/8" />

            {applyDisabled ? (
              <div
                aria-disabled="true"
                className="mt-5 block rounded-sm bg-white/10 py-3 text-center text-sm font-medium text-white/40"
              >
                {t(applyLabelKey)}
              </div>
            ) : (
              <Link
                to={applyHref}
                className="mt-5 block rounded-sm bg-copper py-3 text-center text-sm font-medium text-white transition hover:bg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-card"
              >
                {t(applyLabelKey)}
              </Link>
            )}
          </div>
        </aside>
      </div>

      {/* ── Fixed mobile apply bar ── */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-void/95 px-4 py-3 backdrop-blur-md lg:hidden">
        <div className="mx-auto flex max-w-4xl items-center gap-3">
          {salaryStr && (
            <p className="truncate text-xs font-medium text-copper/80 sm:text-sm">
              {salaryStr}
            </p>
          )}
          {applyDisabled ? (
            <div
              aria-disabled="true"
              className="flex-1 rounded-sm bg-white/10 py-3 text-center text-sm font-medium text-white/40"
            >
              {t(applyLabelKey)}
            </div>
          ) : (
            <Link
              to={applyHref}
              className="flex-1 rounded-sm bg-copper py-3 text-center text-sm font-medium text-white transition hover:bg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-void"
            >
              {t(applyLabelKey)}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

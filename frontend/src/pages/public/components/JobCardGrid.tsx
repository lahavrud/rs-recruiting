import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import FeaturedRibbon from "@/components/ui/FeaturedRibbon";
import type { JobPublicRead } from "@/types/api";
import { formatDate } from "@/utils/formatDate";

import { CardSkeleton } from "./JobBoardSkeletons";

/** Compact card-style salary: "12,000–15,000 ₪", "מ-12,000 ₪", or "עד 15,000 ₪". */
function formatCardSalary(min: number | null, max: number | null): string | null {
  if (min == null && max == null) return null;
  const fmt = (n: number) => n.toLocaleString("he-IL");
  if (min != null && max != null) return `${fmt(min)}–${fmt(max)} ₪`;
  if (min != null) return `מ-${fmt(min)} ₪`;
  return `עד ${fmt(max!)} ₪`;
}

interface JobCardGridProps {
  loading: boolean;
  filtered: JobPublicRead[];
  hasActiveFilter: boolean;
  searchParamsString: string;
  onClearFilters: () => void;
  sentinelRef: (node: HTMLElement | null) => void;
}

export default function JobCardGrid({
  loading,
  filtered,
  hasActiveFilter,
  searchParamsString,
  onClearFilters,
  sentinelRef,
}: JobCardGridProps) {
  const { t } = useTranslation(['common', 'http', 'publicJobs']);

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-white/10 py-16 text-center sm:py-20">
        <p className="text-sm text-white/30">
          {hasActiveFilter
            ? t("publicJobs:board.noResults")
            : t("publicJobs:board.noPositions")}
        </p>
        {hasActiveFilter && (
          <button
            type="button"
            onClick={onClearFilters}
            className="mt-4 text-xs text-copper/70 transition hover:text-copper"
          >
            {t("publicJobs:board.clearFilters")}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
      {filtered.map((job) => (
        <Link
          key={job.id}
          to={{
            pathname: `/jobs/${job.id}`,
            search: searchParamsString,
          }}
          className={[
            "group relative block overflow-hidden rounded-xl border bg-card p-5 transition duration-200 sm:p-6",
            job.is_featured
              ? "border-gold/40 hover:border-gold/60 hover:bg-card-raised"
              : "border-white/8 hover:border-copper/25 hover:bg-card-raised",
          ].join(" ")}
        >
          {job.is_featured && <FeaturedRibbon label={t("publicJobs:board.featured")} />}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="truncate font-medium text-white/85 transition duration-200 group-hover:text-white/95">
                {job.title}
              </h2>
              <p className="mt-1 flex items-center gap-1 text-sm text-white/40">
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
                <span className="truncate">{job.location}</span>
              </p>
            </div>
          </div>
          <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-white/55 sm:line-clamp-none">
            {job.short_description}
          </p>
          {job.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {job.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-copper/25 bg-copper/10 px-2 py-0.5 text-[11px] font-medium text-copper/90"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          <div className="mt-4 flex items-center gap-1.5 text-xs">
            <span className="text-white/35">{t("common:salary")}:</span>
            <span className="font-medium text-copper/85">
              {formatCardSalary(job.salary_min, job.salary_max) ??
                t("common:salaryNotSpecified")}
            </span>
          </div>
          <p className="mt-2 text-xs text-white/25">
            {t("publicJobs:board.posted")} {formatDate(job.created_at)}
          </p>
        </Link>
      ))}
      <div ref={sentinelRef} />
    </div>
  );
}

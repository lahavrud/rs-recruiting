import { useCallback, useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import SeoHead, { SITE_URL, SITE_NAME } from "@/components/ui/SeoHead";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import { getPublicJobs } from "@/services/jobs";
import { errorAlertClsLg } from "@/styles/forms";
import type { JobPublicRead } from "@/types/api";

import JobBoardFilterChip from "./components/JobBoardFilterChip";
import JobBoardFilterPanel from "./components/JobBoardFilterPanel";
import JobBoardHero from "./components/JobBoardHero";
import { FilterSidebarSkeleton, SearchBarSkeleton } from "./components/JobBoardSkeletons";
import { getSalaryBounds, formatSalaryShort } from "./components/jobBoardUtils";
import JobCardGrid from "./components/JobCardGrid";
import MobileFilterDrawer from "./components/MobileFilterDrawer";

import type { SalaryBounds } from "./components/JobBoardFilterPanel";


export default function JobBoardPage() {
  const { t } = useTranslation(['common', 'http', 'https', 'lg', 'publicJobs']);
  const [searchParams, setSearchParams] = useSearchParams();

  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetcher = useCallback((cursor: string | null) => getPublicJobs(cursor), []);
  const {
    items: jobs,
    isLoading: loading,
    error: fetchError,
    sentinelRef,
  } = useInfiniteList<JobPublicRead>(fetcher);

  const initialQuery = searchParams.get("q") ?? "";
  const initialLocationCsv = searchParams.get("loc");
  const initialSmin = searchParams.get("smin");
  const initialSmax = searchParams.get("smax");

  const [query, setQuery] = useState(initialQuery);
  const debouncedQuery = useDebounce(query, 300);
  const [selectedLocations, setSelectedLocations] = useState<string[]>(() =>
    initialLocationCsv ? initialLocationCsv.split(",").filter(Boolean) : [],
  );
  const [salaryRange, setSalaryRange] = useState<[number, number] | null>(() => {
    const lo = initialSmin ? Number(initialSmin) : null;
    const hi = initialSmax ? Number(initialSmax) : null;
    if (lo == null || hi == null || !Number.isFinite(lo) || !Number.isFinite(hi)) return null;
    return [lo, hi];
  });

  // Lock body scroll while the mobile filter drawer is open.
  useEffect(() => {
    if (!drawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [drawerOpen]);

  const onSearch = useCallback((v: string) => setQuery(v), []);

  const uniqueLocations = useMemo(() => {
    const seen = new Set<string>();
    for (const j of jobs) {
      if (j.location) seen.add(j.location.trim());
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b, "he"));
  }, [jobs]);

  const salaryBounds: SalaryBounds = useMemo(() => getSalaryBounds(jobs), [jobs]);

  // Derive the clamped range without storing it — avoids setState-in-effect.
  const effectiveSalaryRange = useMemo<[number, number]>(() => {
    if (!salaryRange) return [salaryBounds.min, salaryBounds.max];
    return [
      Math.max(salaryBounds.min, Math.min(salaryRange[0], salaryBounds.max)),
      Math.max(salaryBounds.min, Math.min(salaryRange[1], salaryBounds.max)),
    ];
  }, [salaryRange, salaryBounds]);

  const isSalaryActive =
    effectiveSalaryRange[0] !== salaryBounds.min ||
    effectiveSalaryRange[1] !== salaryBounds.max;

  // Sync filter state -> URL search params.
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    const setOrDelete = (key: string, val: string | null) => {
      if (val) next.set(key, val);
      else next.delete(key);
    };
    setOrDelete("q", debouncedQuery.trim() || null);
    setOrDelete(
      "loc",
      selectedLocations.length > 0 ? selectedLocations.join(",") : null,
    );
    if (isSalaryActive) {
      setOrDelete("smin", String(effectiveSalaryRange[0]));
      setOrDelete("smax", String(effectiveSalaryRange[1]));
    } else {
      next.delete("smin");
      next.delete("smax");
    }
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, selectedLocations, effectiveSalaryRange, isSalaryActive]);

  const filtered = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return jobs.filter((j) => {
      const requirementsText = j.requirements.map((r) => r.text).join(" ");
      const tagsText = j.tags.join(" ");
      const matchesQuery =
        !q ||
        [
          j.title,
          j.location,
          j.short_description,
          j.description,
          requirementsText,
          tagsText,
        ].some((s) => s.toLowerCase().includes(q));
      const matchesLocation =
        selectedLocations.length === 0 || selectedLocations.includes(j.location.trim());

      let matchesSalary = true;
      if (isSalaryActive) {
        const [filterLo, filterHi] = effectiveSalaryRange;
        // Jobs without any salary information: always show.
        if (j.salary_min != null || j.salary_max != null) {
          // Treat a single-bound job as open-ended on the missing side so a
          // job listing only "מ-10,000 ₪" still matches a filter that caps lower.
          const jobLo = j.salary_min ?? Number.NEGATIVE_INFINITY;
          const jobHi = j.salary_max ?? Number.POSITIVE_INFINITY;
          // Include the job whenever its range overlaps or touches the filter
          // range — e.g. filter 10,000–13,000 includes a 12,000–15,000 role.
          matchesSalary = jobHi >= filterLo && jobLo <= filterHi;
        }
      }

      return matchesQuery && matchesLocation && matchesSalary;
    });
  }, [jobs, debouncedQuery, selectedLocations, effectiveSalaryRange, isSalaryActive]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) + selectedLocations.length + (isSalaryActive ? 1 : 0);
  const hasActiveFilter = activeFilterCount > 0;

  const handleSalaryChange = useCallback((next: [number, number]) => {
    setSalaryRange(next);
  }, []);

  const handleResetSalary = useCallback(() => {
    setSalaryRange([salaryBounds.min, salaryBounds.max]);
  }, [salaryBounds]);

  const clearFilters = useCallback(() => {
    setQuery("");
    setSelectedLocations([]);
    setSalaryRange(null);
  }, []);

  const structuredData = useMemo(() => {
    const breadcrumb = {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
        {
          "@type": "ListItem",
          position: 2,
          name: t("publicJobs:board.title"),
          item: `${SITE_URL}/jobs`,
        },
      ],
    };
    if (loading || jobs.length === 0) {
      return { "@context": "https://schema.org", "@graph": [breadcrumb] };
    }
    const itemList = {
      "@type": "ItemList",
      name: t("publicJobs:board.title"),
      url: `${SITE_URL}/jobs`,
      numberOfItems: jobs.length,
      itemListElement: jobs.slice(0, 10).map((job, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: job.title,
        url: `${SITE_URL}/jobs/${job.id}`,
      })),
    };
    return { "@context": "https://schema.org", "@graph": [breadcrumb, itemList] };
  }, [loading, jobs, t]);

  if (fetchError) {
    return (
      <div className={`${errorAlertClsLg} text-center`}>
        {t("publicJobs:board.errorLoad")}
      </div>
    );
  }

  const baseFilterPanelProps = {
    query,
    onQueryChange: setQuery,
    locations: uniqueLocations,
    selectedLocations,
    onLocationsChange: setSelectedLocations,
    salaryBounds,
    salaryRange: effectiveSalaryRange,
    onSalaryChange: handleSalaryChange,
    isSalaryActive,
    onResetSalary: handleResetSalary,
    hasActiveFilter,
    onClearAll: clearFilters,
  } as const;

  const showFilters = !loading && jobs.length > 0;

  return (
    <div className="pb-14">
      <SeoHead
        title={t("publicJobs:board.title")}
        description={t("publicJobs:board.subtitle")}
        canonical={`${SITE_URL}/jobs`}
        ogImage={`${SITE_URL}/og/jobs.svg`}
        structuredData={structuredData}
      />

      <JobBoardHero initialQuery={initialQuery} onSearch={onSearch} />

      {/* ── Job list ────────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-4xl px-6 pt-10">
        <div
          className={
            loading || showFilters ? "lg:grid lg:grid-cols-[240px_1fr] lg:gap-8" : ""
          }
        >
          {/* Filter sidebar — sticky offset accounts for fixed navbar */}
          {loading ? (
            <aside className="hidden lg:sticky lg:top-28 lg:block lg:self-start">
              <FilterSidebarSkeleton />
            </aside>
          ) : showFilters ? (
            <aside className="hidden lg:sticky lg:top-28 lg:block lg:self-start">
              <div className="rounded-xl border border-white/8 bg-card-raised/40 p-5">
                <p className="mb-4 text-sm font-medium text-white/85">
                  {t("publicJobs:board.filters")}
                </p>
                <JobBoardFilterPanel {...baseFilterPanelProps} />
              </div>
            </aside>
          ) : null}

          {/* Results column */}
          <div className="min-w-0">
            {/* Mobile filter trigger (search bar is in hero) */}
            {loading && <SearchBarSkeleton />}
            {!loading && jobs.length > 0 && (
              <div className="mb-5 flex items-stretch gap-2">
                <div className="flex-1" />
                {showFilters && (
                  <button
                    type="button"
                    onClick={() => setDrawerOpen(true)}
                    className="relative inline-flex shrink-0 items-center gap-1.5 rounded-md border border-white/15 bg-card-raised/40 px-3 text-sm font-medium text-white/75 transition hover:border-copper/40 hover:text-white lg:hidden"
                    aria-label={t("publicJobs:board.openFilters")}
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
                        d="M2 4a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4Zm2 4a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5A.75.75 0 0 1 4 8Zm2 4a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5h-2.5A.75.75 0 0 1 6 12Z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {t("publicJobs:board.filters")}
                    {activeFilterCount > 0 && (
                      <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
                        {activeFilterCount}
                      </span>
                    )}
                  </button>
                )}
              </div>
            )}

            {!loading && hasActiveFilter && (
              <div className="mb-4 space-y-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  {query.trim() && (
                    <JobBoardFilterChip
                      label={`${t("common:search")}: "${query.trim()}"`}
                      onRemove={() => setQuery("")}
                    />
                  )}
                  {selectedLocations.map((loc) => (
                    <JobBoardFilterChip
                      key={`loc-${loc}`}
                      label={`${t("publicJobs:board.locationLabel")}: ${loc}`}
                      onRemove={() =>
                        setSelectedLocations((prev) => prev.filter((x) => x !== loc))
                      }
                    />
                  ))}
                  {isSalaryActive && (
                    <JobBoardFilterChip
                      label={`${t("publicJobs:board.salaryRange")}: ${formatSalaryShort(effectiveSalaryRange[0])} – ${formatSalaryShort(effectiveSalaryRange[1])}`}
                      onRemove={handleResetSalary}
                    />
                  )}
                </div>
                <p className="text-xs text-white/40">
                  {filtered.length === 1
                    ? t("publicJobs:board.resultsCount.one")
                    : t("publicJobs:board.resultsCount.other", { count: filtered.length })}
                </p>
              </div>
            )}

            <JobCardGrid
              loading={loading}
              filtered={filtered}
              hasActiveFilter={hasActiveFilter}
              searchParamsString={searchParams.toString()}
              onClearFilters={clearFilters}
              sentinelRef={sentinelRef}
            />
          </div>
        </div>

        {/* Mobile filter drawer — portaled to body so it escapes the page-enter
            transform (which creates a containing block for fixed elements). */}
        {showFilters && (
          <MobileFilterDrawer
            {...baseFilterPanelProps}
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            filteredCount={filtered.length}
          />
        )}
      </div>
    </div>
  );
}

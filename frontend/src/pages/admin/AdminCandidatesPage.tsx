import { useCallback, useEffect, useMemo, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import FunnelIcon from "@/components/admin/FunnelIcon";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import NoResults from "@/components/ui/NoResults";
import PageHeader from "@/components/ui/PageHeader";
import SearchInput from "@/components/ui/SearchInput";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { getApplications } from "@/services/adminApplications";
import { deleteCandidate, getCandidate, getCandidates } from "@/services/adminCandidates";
import { getActiveCompanies } from "@/services/adminCompanies";
import { getJobs } from "@/services/adminJobs";
import type { ApplicationWithDetails, CandidateProfileRead } from "@/types/api";
import { apiErrorKey } from "@/utils/apiError";

import CandidateDetailDialog from "./components/CandidateDetailDialog";
import CandidateEditDialog from "./components/CandidateEditDialog";
import CandidatesFilterPanel from "./components/CandidatesFilterPanel";
import CandidatesMobileList from "./components/CandidatesMobileList";
import CandidatesTable from "./components/CandidatesTable";

export default function AdminCandidatesPage() {
  const { t } = useTranslation(['admin', 'common', 'md']);
  usePageTitle(t("admin:candidates.title"));
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<CandidateProfileRead>> =>
      getCandidates({ cursor }),
    [],
  );

  const {
    items: candidates,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    updateItem,
    removeItem,
  } = useInfiniteList<CandidateProfileRead>(fetcher);

  const [detail, setDetail] = useState<CandidateProfileRead | null>(null);
  const [editing, setEditing] = useState<CandidateProfileRead | null>(null);
  const [deletePending, setDeletePending] = useState<CandidateProfileRead | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);

  // Client-side filters on the loaded candidate set.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [filterOpen, setFilterOpen] = useState(false);
  const [jobFilter, setJobFilter] = useState<number[]>([]);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);

  // Cache jobs + companies for the filter selects, and applications for the
  // candidate→job / candidate→company lookup.
  const [allJobs, setAllJobs] = useState<{ id: number; title: string; company_id: number }[]>([]);
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(
    new Map(),
  );
  const [jobTitleById, setJobTitleById] = useState<Map<number, string>>(new Map());
  const [appCache, setAppCache] = useState<ApplicationWithDetails[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      getJobs({ limit: 100 }, ctrl.signal),
      getActiveCompanies({ limit: 100 }, ctrl.signal),
      getApplications({ limit: 100 }, ctrl.signal),
    ])
      .then(([jobsPage, companiesPage, appsPage]) => {
        setAllJobs(
          jobsPage.items.map((j) => ({
            id: j.id,
            title: j.title,
            company_id: j.company_id,
          })),
        );
        setJobTitleById(new Map(jobsPage.items.map((j) => [j.id, j.title])));
        setCompanyNameById(
          new Map(
            companiesPage.items.map((row) => [
              row.company_profile.id,
              row.company_profile.name,
            ]),
          ),
        );
        setAppCache(appsPage.items);
      })
      .catch(() => {
        /* best-effort */
      });
    return () => ctrl.abort();
  }, []);

  // candidate_id → set of job IDs / company IDs they applied to.
  const candidateAppliedJobs = useMemo(() => {
    const map = new Map<number, Set<number>>();
    for (const a of appCache) {
      if (!map.has(a.candidate_id)) map.set(a.candidate_id, new Set());
      map.get(a.candidate_id)?.add(a.job_id);
    }
    return map;
  }, [appCache]);

  const candidateAppliedCompanies = useMemo(() => {
    const map = new Map<number, Set<number>>();
    for (const a of appCache) {
      if (!map.has(a.candidate_id)) map.set(a.candidate_id, new Set());
      map.get(a.candidate_id)?.add(a.job.company_id);
    }
    return map;
  }, [appCache]);

  const filteredCandidates = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return candidates.filter((c) => {
      if (jobFilter.length > 0) {
        const jobs = candidateAppliedJobs.get(c.id);
        if (!jobs || !jobFilter.some((id) => jobs.has(id))) return false;
      }
      if (companyFilter.length > 0) {
        const companies = candidateAppliedCompanies.get(c.id);
        if (!companies || !companyFilter.some((id) => companies.has(id))) return false;
      }
      if (!q) return true;
      return [c.full_name, c.email, c.phone ?? "", c.linkedin_url ?? ""].some((s) =>
        s.toLowerCase().includes(q),
      );
    });
  }, [
    candidates,
    debouncedQuery,
    jobFilter,
    companyFilter,
    candidateAppliedJobs,
    candidateAppliedCompanies,
  ]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) + jobFilter.length + companyFilter.length;

  // Auto-open detail modal when navigated from another page via ?detail=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    const ctrl = new AbortController();
    window.history.replaceState({}, "", window.location.pathname);
    getCandidate(Number(id), ctrl.signal)
      .then((c) => setDetail(c))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        toast.error(t(apiErrorKey(e)));
      });
    return () => ctrl.abort();
  }, [t, toast]);

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setPendingDelete(true);
    try {
      await deleteCandidate(deletePending.id);
      removeItem((c) => c.id === deletePending.id);
      toast.success(t("admin:candidates.deletedToast"));
      setDeletePending(null);
      setDetail(null);
    } catch {
      toast.error(t("admin:candidates.errors.deleteFailed"));
    } finally {
      setPendingDelete(false);
    }
  }

  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin:candidates.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin:candidates.title")}
        subtitle={t("admin:candidates.subtitle")}
      />

      {/* Search + filter trigger */}
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin:candidates.searchPlaceholder")}
            clearable
          />
        </div>
        <button
          type="button"
          onClick={() => setFilterOpen((o) => !o)}
          aria-expanded={filterOpen}
          aria-label={t("admin:candidates.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            filterOpen
              ? "border-copper/50 bg-copper/10 text-white"
              : "border-white/15 bg-card-raised/40 text-white/75 hover:border-copper/40 hover:text-white"
          }`}
        >
          <FunnelIcon />
          <span className="hidden sm:inline">{t("admin:candidates.filters")}</span>
          {activeFilterCount > 0 && (
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {activeFilterCount > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common:search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {jobFilter.map((id) => (
            <ActiveFilterChip
              key={`job-${id}`}
              label={`${t("admin:candidates.filterByJob")}: ${jobTitleById.get(id) ?? `#${id}`}`}
              onRemove={() => setJobFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin:candidates.filterByCompany")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() => setCompanyFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
        </div>
      )}

      <CandidatesFilterPanel
        filterOpen={filterOpen}
        companyFilter={companyFilter}
        setCompanyFilter={setCompanyFilter}
        jobFilter={jobFilter}
        setJobFilter={setJobFilter}
        allJobs={allJobs}
        companyNameById={companyNameById}
      />

      {isLoading ? (
        <>
          <div className="md:hidden">
            <MobileListSkeleton rows={6} />
          </div>
          <div className="hidden md:block">
            <TableSkeleton rows={6} columns={4} />
          </div>
        </>
      ) : error ? (
        <ErrorState message={t("admin:candidates.loadError")} onRetry={reload} />
      ) : candidates.length === 0 ? (
        <EmptyState
          eyebrow={t("admin:candidates.title")}
          headline={t("admin:candidates.empty")}
        />
      ) : filteredCandidates.length === 0 ? (
        <NoResults />
      ) : (
        <>
          <CandidatesMobileList
            candidates={filteredCandidates}
            onEdit={setEditing}
            onDelete={setDeletePending}
          />

          <CandidatesTable
            candidates={filteredCandidates}
            onView={setDetail}
            onEdit={setEditing}
            onDelete={setDeletePending}
            sentinelRef={sentinelRef}
            isFetchingMore={isFetchingMore}
          />
        </>
      )}

      <CandidateDetailDialog
        candidate={detail}
        onClose={() => setDetail(null)}
        onEdit={() => {
          if (detail) setEditing(detail);
          setDetail(null);
        }}
        onDelete={() => {
          if (detail) setDeletePending(detail);
          setDetail(null);
        }}
      />

      <CandidateEditDialog
        candidate={editing}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          updateItem((c) => c.id === updated.id, updated);
          toast.success(t("admin:candidates.savedToast"));
          setEditing(null);
        }}
        onError={() => toast.error(t("admin:candidates.errors.saveFailed"))}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin:candidates.deleteConfirmTitle", {
          name: deletePending?.full_name ?? "",
        })}
        message={t("admin:candidates.deleteConfirmMessage")}
        confirmLabel={t("admin:candidates.deleteConfirmYes")}
        variant="danger"
        isPending={pendingDelete}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

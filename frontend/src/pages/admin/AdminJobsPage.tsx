import { useCallback, useEffect, useMemo, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import NoResults from "@/components/ui/NoResults";
import PageHeader from "@/components/ui/PageHeader";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { JOB_STATUS_COLORS } from "@/constants/statusColors";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { getActiveCompanies } from "@/services/adminCompanies";
import {
  approveJob,
  deleteJob,
  getJob,
  getJobs,
  rejectJob,
} from "@/services/adminJobs";
import { JobStatus } from "@/types/api";
import type { JobRead } from "@/types/api";
import { apiErrorKey } from "@/utils/apiError";

import JobCreateDialog from "./components/JobCreateDialog";
import JobDialog from "./components/JobDialog";
import JobsFilterPanel from "./components/JobsFilterPanel";
import JobsList from "./components/JobsList";
import JobsTable from "./components/JobsTable";

const ALL_STATUSES = [
  JobStatus.PENDING_APPROVAL,
  JobStatus.PUBLISHED,
  JobStatus.CLOSED,
];

const ALL_FILTER = "ALL";
type FilterValue = string;

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminJobsPage() {
  const { t } = useTranslation(['admin', 'md', 'publicJobs']);
  usePageTitle(t("admin:jobs.title"));
  const toast = useToast();

  const [filter, setFilter] = useState<FilterValue>(() => {
    const s = new URLSearchParams(window.location.search).get("status");
    if (
      s === JobStatus.PENDING_APPROVAL ||
      s === JobStatus.PUBLISHED ||
      s === JobStatus.CLOSED
    ) {
      return s;
    }
    return ALL_FILTER;
  });

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<JobRead>> => {
      const params: { status?: JobStatus; cursor: string | null } = { cursor };
      if (filter !== ALL_FILTER) params.status = filter as JobStatus;
      return getJobs(params);
    },
    [filter],
  );

  const {
    items: jobs,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    prependItem,
    updateItem,
    removeItem,
  } = useInfiniteList<JobRead>(fetcher);

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [detail, setDetail] = useState<JobRead | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletePending, setDeletePending] = useState<JobRead | null>(null);
  const [rejectPending, setRejectPending] = useState<JobRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);

  // Client-side filters (applied to the loaded set).
  // Status is the only filter that re-fetches server-side (see fetcher above);
  // everything else narrows the in-memory result.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [salaryRange, setSalaryRange] = useState<[number, number] | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);

  const uniqueLocations = useMemo(() => {
    const seen = new Set<string>();
    for (const j of jobs) if (j.location) seen.add(j.location.trim());
    return Array.from(seen).sort((a, b) => a.localeCompare(b, "he"));
  }, [jobs]);

  const uniqueCompanies = useMemo(() => {
    const seen = new Set<number>();
    for (const j of jobs) seen.add(j.company_id);
    return Array.from(seen);
  }, [jobs]);

  const salaryBounds = useMemo(() => {
    let lo = Infinity, hi = -Infinity;
    for (const j of jobs) {
      if (j.salary_min != null) lo = Math.min(lo, j.salary_min);
      if (j.salary_max != null) hi = Math.max(hi, j.salary_max);
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo >= hi) {
      return { min: 0, max: 50000 };
    }
    return { min: Math.floor(lo / 500) * 500, max: Math.ceil(hi / 500) * 500 };
  }, [jobs]);

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

  const filteredJobs = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return jobs.filter((j) => {
      if (q) {
        const reqsText = j.requirements.map((r) => r.text).join(" ");
        const tagsText = j.tags.join(" ");
        const matches = [
          j.title,
          j.location,
          j.short_description,
          j.description,
          reqsText,
          tagsText,
        ].some((s) => s.toLowerCase().includes(q));
        if (!matches) return false;
      }
      if (selectedLocations.length > 0 && !selectedLocations.includes(j.location.trim())) return false;
      if (companyFilter.length > 0 && !companyFilter.includes(j.company_id)) return false;
      if (featuredOnly && !j.is_featured) return false;
      if (isSalaryActive) {
        const [filterLo, filterHi] = effectiveSalaryRange;
        if (j.salary_min != null || j.salary_max != null) {
          const jobLo = j.salary_min ?? Number.NEGATIVE_INFINITY;
          const jobHi = j.salary_max ?? Number.POSITIVE_INFINITY;
          if (!(jobHi >= filterLo && jobLo <= filterHi)) return false;
        }
      }
      return true;
    });
  }, [
    jobs,
    debouncedQuery,
    selectedLocations,
    companyFilter,
    featuredOnly,
    effectiveSalaryRange,
    isSalaryActive,
  ]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) +
    selectedLocations.length +
    companyFilter.length +
    (featuredOnly ? 1 : 0) +
    (isSalaryActive ? 1 : 0);

  function clearFilters() {
    setQuery("");
    setSelectedLocations([]);
    setCompanyFilter([]);
    setFeaturedOnly(false);
    setSalaryRange(null);
  }

  // Load company names + emails for the filter chip and the mailto action.
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(
    new Map(),
  );
  const [companyEmailById, setCompanyEmailById] = useState<Map<number, string>>(
    new Map(),
  );
  useEffect(() => {
    if (uniqueCompanies.length === 0) return;
    const ctrl = new AbortController();
    getActiveCompanies({ limit: 100 }, ctrl.signal)
      .then((page) => {
        const names = new Map<number, string>();
        const emails = new Map<number, string>();
        for (const row of page.items) {
          names.set(row.company_profile.id, row.company_profile.name);
          if (row.user?.email) {
            emails.set(row.company_profile.id, row.user.email);
          }
        }
        setCompanyNameById(names);
        setCompanyEmailById(emails);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [uniqueCompanies.length]);

  function openMailToCompany(job: JobRead) {
    const email = companyEmailById.get(job.company_id);
    if (!email) {
      toast.error(t("admin:jobs.emailNoAddress"));
      return;
    }
    const subject = encodeURIComponent(
      t("admin:jobs.emailSubjectPrefix", { title: job.title }),
    );
    window.open(`mailto:${email}?subject=${subject}`, "_self");
  }

  // Sync ?job=<id> URL param to detail state — enables direct links and back-button close.
  // effectiveDetail is derived so the dialog closes instantly when the URL param disappears
  // (back button), without a synchronous setState in the effect body.
  const jobIdFromUrl = searchParams.get("job");
  const effectiveDetail = jobIdFromUrl ? detail : null;
  useEffect(() => {
    if (!jobIdFromUrl) return;
    const id = Number(jobIdFromUrl);
    if (Number.isNaN(id)) return;
    const ctrl = new AbortController();
    getJob(id, ctrl.signal)
      .then(setDetail)
      .catch((e) => {
        if (axios.isCancel(e)) return;
        toast.error(t(apiErrorKey(e)));
      });
    return () => ctrl.abort();
  }, [jobIdFromUrl, t, toast]);

  function openJob(job: JobRead) {
    setDetail(job);
    navigate(`/admin/jobs?job=${job.id}`);
  }

  function closeJob() {
    setDetail(null);
    navigate("/admin/jobs", { replace: true });
  }

  // Convert legacy ?detail=<id> param (used by other admin pages) to ?job=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    navigate(`/admin/jobs?job=${id}`, { replace: true });
  }, [navigate]);

  const STATUS_LABELS: Record<string, string> = {
    PENDING_APPROVAL: t("admin:jobs.statusLabels.PENDING_APPROVAL"),
    PUBLISHED: t("admin:jobs.statusLabels.PUBLISHED"),
    CLOSED: t("admin:jobs.statusLabels.CLOSED"),
  };

  async function handleApprove(job: JobRead) {
    try {
      const updated = await approveJob(job.id);
      updateItem((j) => j.id === job.id, updated);
      toast.success(t("admin:jobs.approvedToast"));
    } catch {
      toast.error(t("admin:jobs.approveError"));
    }
  }

  async function handleRejectConfirm() {
    if (!rejectPending) return;
    setPendingMutation(true);
    try {
      await rejectJob(rejectPending.id);
      // Backend sets status to CLOSED on reject
      updateItem((j) => j.id === rejectPending.id, {
        ...rejectPending,
        status: JobStatus.CLOSED,
      });
      toast.success(t("admin:jobs.rejectedToast"));
      setRejectPending(null);
    } catch {
      toast.error(t("admin:jobs.rejectError"));
    } finally {
      setPendingMutation(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setPendingMutation(true);
    try {
      await deleteJob(deletePending.id);
      removeItem((j) => j.id === deletePending.id);
      toast.success(t("admin:jobs.deletedToast"));
      setDeletePending(null);
      closeJob();
    } catch {
      toast.error(t("admin:jobs.errors.deleteFailed"));
    } finally {
      setPendingMutation(false);
    }
  }

  const filterTabs: FilterValue[] = [ALL_FILTER, ...ALL_STATUSES];

  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin:jobs.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin:jobs.title")}
        subtitle={t("admin:jobs.subtitle")}
        action={
          <Button onClick={() => setCreating(true)}>
            {t("admin:jobs.newJob")}
          </Button>
        }
      />

      <JobsFilterPanel
        search={{ query, setQuery }}
        filters={{
          filter,
          setFilter,
          filterTabs,
          statusLabels: STATUS_LABELS,
          uniqueLocations,
          selectedLocations,
          setSelectedLocations,
          featuredOnly,
          setFeaturedOnly,
        }}
        salary={{
          salaryBounds,
          effectiveSalaryRange,
          isSalaryActive,
          setSalaryRange,
        }}
        company={{
          uniqueCompanies,
          companyFilter,
          setCompanyFilter,
          companyNameById,
        }}
        ui={{
          activeFilterCount,
          filterOpen,
          setFilterOpen,
          clearFilters,
        }}
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
        <ErrorState message={t("admin:jobs.loadError")} onRetry={reload} />
      ) : jobs.length === 0 ? (
        <EmptyState eyebrow={t("admin:jobs.title")} headline={t("admin:jobs.empty")} />
      ) : filteredJobs.length === 0 ? (
        <NoResults>
          <button
            type="button"
            onClick={clearFilters}
            className="mt-3 text-xs text-copper/70 transition hover:text-copper"
          >
            {t("publicJobs:board.clearFilters")}
          </button>
        </NoResults>
      ) : (
        <>
          <JobsList
            jobs={filteredJobs}
            statusLabels={STATUS_LABELS}
            statusColors={JOB_STATUS_COLORS}
            companyNameById={companyNameById}
            onEdit={openJob}
            onApprove={handleApprove}
            onReject={setRejectPending}
            onDelete={setDeletePending}
            onMailto={openMailToCompany}
          />

          <JobsTable
            jobs={filteredJobs}
            statusLabels={STATUS_LABELS}
            statusColors={JOB_STATUS_COLORS}
            onOpenDetail={openJob}
            onEdit={openJob}
            onApprove={handleApprove}
            onReject={setRejectPending}
            onDelete={setDeletePending}
            onMailto={openMailToCompany}
          />

          <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
        </>
      )}

      <JobDialog
        job={effectiveDetail}
        companyName={effectiveDetail ? companyNameById.get(effectiveDetail.company_id) : undefined}
        onClose={closeJob}
        onSaved={(updated) => {
          updateItem((j) => j.id === updated.id, updated);
          setDetail(updated);
          toast.success(t("admin:jobs.savedToast"));
        }}
        onError={() => toast.error(t("admin:jobs.errors.saveFailed"))}
        onDelete={() => {
          if (effectiveDetail) setDeletePending(effectiveDetail);
          closeJob();
        }}
        onApprove={() => {
          if (effectiveDetail) handleApprove(effectiveDetail);
          closeJob();
        }}
        onReject={() => {
          if (effectiveDetail) setRejectPending(effectiveDetail);
          closeJob();
        }}
      />

      <JobCreateDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(created) => {
          prependItem(created);
          toast.success(t("admin:jobs.createdToast"));
          setCreating(false);
        }}
        onError={() => toast.error(t("admin:jobs.errors.createFailed"))}
      />

      <ConfirmDialog
        open={rejectPending != null}
        onOpenChange={(o) => !o && setRejectPending(null)}
        title={t("admin:jobs.rejectConfirmTitle")}
        message={t("admin:jobs.rejectConfirm")}
        confirmLabel={t("admin:jobs.reject")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleRejectConfirm}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin:jobs.deleteConfirmTitle")}
        message={t("admin:jobs.deleteConfirmMessage")}
        confirmLabel={t("admin:jobs.deleteConfirmYes")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

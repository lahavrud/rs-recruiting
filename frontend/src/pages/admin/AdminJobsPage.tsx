import { useCallback, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SortControl from "@/components/admin/SortControl";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
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
import { useSortChain } from "@/hooks/useSortChain";
import { useToast } from "@/hooks/useToast";
import {
  approveJob,
  deleteJob,
  getJobs,
  rejectJob,
} from "@/services/adminJobs";
import { JobStatus } from "@/types/enums";
import type { JobRead } from "@/types/jobs";

import ContactJobDialog from "./components/ContactJobDialog";
import JobCreateDialog from "./components/JobCreateDialog";
import JobDialog from "./components/JobDialog";
import JobRecordPane from "./components/JobRecordPane";
import JobsFilterPanel from "./components/JobsFilterPanel";
import JobsList from "./components/JobsList";
import JobsRailList from "./components/JobsRailList";
import JobsTable from "./components/JobsTable";

const ALL_STATUSES = [
  JobStatus.PENDING_APPROVAL,
  JobStatus.PUBLISHED,
  JobStatus.CLOSED,
];

const ALL_FILTER = "ALL";
type FilterValue = string;
type JobSortColumn = "name" | "created_at" | "status";
const naturalOrder = (column: JobSortColumn): "asc" | "desc" =>
  column === "created_at" ? "desc" : "asc";

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminJobsPage() {
  const { t } = useTranslation(["admin", "md", "publicJobs"]);
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

  const { chain, click, replace } = useSortChain<JobSortColumn>([
    { column: "status", order: "asc" },
    { column: "created_at", order: "desc" },
  ]);
  const handleSort = (column: JobSortColumn) => click(column, naturalOrder(column));
  const [primary, secondary] = chain;
  const { column: sort, order } = primary;
  const sort2 = secondary?.column;
  const order2 = secondary?.order;
  const columnState = (column: JobSortColumn) => {
    const idx = chain.findIndex((key) => key.column === column);
    if (idx === -1) return { active: false, order: "desc" as const, rank: undefined };
    return {
      active: true,
      order: chain[idx].order,
      rank: chain.length > 1 ? ((idx + 1) as 1 | 2) : undefined,
    };
  };

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<JobRead>> => {
      const params: { status?: JobStatus; cursor: string | null } = { cursor };
      if (filter !== ALL_FILTER) params.status = filter as JobStatus;
      return getJobs({ ...params, sort, order, sort2, order2 });
    },
    [filter, sort, order, sort2, order2],
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
  const { id } = useParams<{ id: string }>();
  const selectedId = id != null ? Number(id) : null;

  const [detail, setDetail] = useState<JobRead | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [deletePending, setDeletePending] = useState<JobRead | null>(null);
  const [rejectPending, setRejectPending] = useState<JobRead | null>(null);
  const [contactPending, setContactPending] = useState<JobRead | null>(null);
  const [isPendingMutation, setIsPendingMutation] = useState(false);

  // Client-side filters (applied to the loaded set).
  // Status is the only filter that re-fetches server-side (see fetcher above);
  // everything else narrows the in-memory result.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);
  const [isFeaturedOnly, setIsFeaturedOnly] = useState(false);
  const [salaryRange, setSalaryRange] = useState<[number, number] | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const uniqueLocations = useMemo(() => {
    const seen = new Set<string>();
    for (const j of jobs) if (j.location) seen.add(j.location.trim());
    return Array.from(seen).sort((a, b) => a.localeCompare(b, "he"));
  }, [jobs]);

  const uniqueCompanies = useMemo(() => {
    const seen = new Map<number, string>();
    for (const j of jobs) seen.set(j.company_id, j.company_name);
    return Array.from(seen.keys());
  }, [jobs]);

  const companyNameById = useMemo(
    () => new Map(jobs.map((j) => [j.company_id, j.company_name])),
    [jobs],
  );

  const salaryBounds = useMemo(() => {
    let lo = Infinity,
      hi = -Infinity;
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
      if (
        selectedLocations.length > 0 &&
        !selectedLocations.includes(j.location.trim())
      )
        return false;
      if (companyFilter.length > 0 && !companyFilter.includes(j.company_id))
        return false;
      if (isFeaturedOnly && !j.is_featured) return false;
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
    isFeaturedOnly,
    effectiveSalaryRange,
    isSalaryActive,
  ]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) +
    selectedLocations.length +
    companyFilter.length +
    (isFeaturedOnly ? 1 : 0) +
    (isSalaryActive ? 1 : 0);

  function clearFilters() {
    setQuery("");
    setSelectedLocations([]);
    setCompanyFilter([]);
    setIsFeaturedOnly(false);
    setSalaryRange(null);
  }

  function openContactJob(job: JobRead) {
    setContactPending(job);
  }

  const selectedJob = selectedId != null ? jobs.find((j) => j.id === selectedId) : undefined;

  function openEdit(job: JobRead) {
    setDetail(job);
  }

  function closeEdit() {
    setDetail(null);
  }

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
    setIsPendingMutation(true);
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
      setIsPendingMutation(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setIsPendingMutation(true);
    try {
      await deleteJob(deletePending.id);
      removeItem((j) => j.id === deletePending.id);
      toast.success(t("admin:jobs.deletedToast"));
      setDeletePending(null);
      if (selectedId === deletePending.id) {
        navigate("/admin/jobs");
      }
    } catch {
      toast.error(t("admin:jobs.errors.deleteFailed"));
    } finally {
      setIsPendingMutation(false);
    }
  }

  const filterTabs: FilterValue[] = [ALL_FILTER, ...ALL_STATUSES];

  const sortControl = (
    <SortControl
      ariaLabel={t("admin:jobs.sort.label")}
      value={`${sort}:${order}`}
      onChange={(col, ord) => replace(col as JobSortColumn, ord)}
      options={[
        { value: "status:asc", label: t("admin:jobs.sort.statusAsc") },
        { value: "status:desc", label: t("admin:jobs.sort.statusDesc") },
        { value: "created_at:desc", label: t("admin:jobs.sort.dateDesc") },
        { value: "created_at:asc", label: t("admin:jobs.sort.dateAsc") },
        { value: "name:asc", label: t("admin:jobs.sort.nameAsc") },
        { value: "name:desc", label: t("admin:jobs.sort.nameDesc") },
      ]}
    />
  );

  const header = (
    <>
      <h1 data-page-heading className="sr-only">
        {t("admin:jobs.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin:jobs.title")}
        subtitle={t("admin:jobs.subtitle")}
        action={
          <Button onClick={() => setIsCreating(true)}>{t("admin:jobs.newJob")}</Button>
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
          isFeaturedOnly,
          setIsFeaturedOnly,
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
          isFilterOpen,
          setIsFilterOpen,
          clearFilters,
        }}
      />
    </>
  );

  const listStateProps = {
    isLoading,
    error,
    onRetry: reload,
    errorMessage: t("admin:jobs.loadError"),
    isEmpty: filteredJobs.length === 0,
    hasQuery: activeFilterCount > 0,
    emptyEyebrow: t("admin:jobs.title"),
    emptyHeadline: t("admin:jobs.empty"),
  };

  const dialogs = (
    <>
      <ContactJobDialog
        job={contactPending}
        companyName={contactPending ? companyNameById.get(contactPending.company_id) : undefined}
        onClose={() => setContactPending(null)}
      />
      <JobDialog
        job={detail}
        companyName={detail ? companyNameById.get(detail.company_id) : undefined}
        onClose={closeEdit}
        onSaved={(updated) => {
          updateItem((j) => j.id === updated.id, updated);
          setDetail(updated);
          toast.success(t("admin:jobs.savedToast"));
        }}
        onError={() => toast.error(t("admin:jobs.errors.saveFailed"))}
        onDelete={() => {
          if (detail) setDeletePending(detail);
          closeEdit();
        }}
        onApprove={() => {
          if (detail) handleApprove(detail);
          closeEdit();
        }}
        onReject={() => {
          if (detail) setRejectPending(detail);
          closeEdit();
        }}
      />
      <JobCreateDialog
        open={isCreating}
        onClose={() => setIsCreating(false)}
        onCreated={(created) => {
          prependItem(created);
          toast.success(t("admin:jobs.createdToast"));
          setIsCreating(false);
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
        isPending={isPendingMutation}
        onConfirm={handleRejectConfirm}
      />
      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin:jobs.deleteConfirmTitle")}
        message={t("admin:jobs.deleteConfirmMessage")}
        confirmLabel={t("admin:jobs.deleteConfirmYes")}
        variant="danger"
        isPending={isPendingMutation}
        onConfirm={handleDeleteConfirm}
      />
    </>
  );

  if (selectedId == null) {
    return (
      <div>
        {header}
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
            <div className="mb-3 md:hidden">
              {sortControl}
            </div>
            <JobsList
              jobs={filteredJobs}
              statusLabels={STATUS_LABELS}
              statusColors={JOB_STATUS_COLORS}
              companyNameById={companyNameById}
              onEdit={openEdit}
              onApprove={handleApprove}
              onReject={setRejectPending}
              onDelete={setDeletePending}
              onMailto={openContactJob}
            />
            <JobsTable
              jobs={filteredJobs}
              columnState={columnState}
              onSort={handleSort}
              statusLabels={STATUS_LABELS}
              statusColors={JOB_STATUS_COLORS}
              onOpenDetail={(j) => navigate(`/admin/jobs/${j.id}`)}
              onEdit={openEdit}
              onApprove={handleApprove}
              onReject={setRejectPending}
              onDelete={setDeletePending}
              onMailto={openContactJob}
            />
            <InfiniteScrollFooter
              sentinelRef={sentinelRef}
              isFetchingMore={isFetchingMore}
            />
          </>
        )}
        {dialogs}
      </div>
    );
  }

  return (
    <SplitPaneLayout
      recordPresent={selectedId != null}
      showListLabel={t("admin:jobs.record.showList")}
      hideListLabel={t("admin:jobs.record.hideList")}
      rail={
        <>
          {header}
          <div className="mb-3">{sortControl}</div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <ListStateSwitch
              {...listStateProps}
              loading={<MobileListSkeleton rows={6} />}
            >
              <JobsRailList
                jobs={filteredJobs}
                selectedId={selectedId}
                statusLabels={STATUS_LABELS}
                onView={(j) => navigate(`/admin/jobs/${j.id}`)}
                onEdit={openEdit}
                onApprove={handleApprove}
                onReject={setRejectPending}
                onDelete={setDeletePending}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />
            </ListStateSwitch>
          </div>
        </>
      }
      record={
        <JobRecordPane
          jobId={selectedId}
          job={selectedJob}
          companyNameById={companyNameById}
          onEdit={openEdit}
          onApprove={handleApprove}
          onReject={setRejectPending}
          onDelete={setDeletePending}
        />
      }
    >
      {dialogs}
    </SplitPaneLayout>
  );
}

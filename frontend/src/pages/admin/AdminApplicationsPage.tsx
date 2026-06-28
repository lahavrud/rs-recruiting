import { useCallback, useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import FunnelIcon from "@/components/admin/FunnelIcon";
import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SortControl from "@/components/admin/SortControl";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import PageHeader from "@/components/ui/PageHeader";
import SearchInput from "@/components/ui/SearchInput";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { APPLICATION_STATUS_COLORS } from "@/constants/statusColors";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useSortChain } from "@/hooks/useSortChain";
import { useToast } from "@/hooks/useToast";
import {
  deleteApplication,
  getApplications,
  type ApplicationListParams,
} from "@/services/adminApplications";
import { getJobs } from "@/services/adminJobs";
import { type ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";

import ApplicationNotesDialog from "./components/ApplicationNotesDialog";
import ApplicationRecordPane from "./components/ApplicationRecordPane";
import ApplicationsFilterPanel from "./components/ApplicationsFilterPanel";
import ApplicationsRailList from "./components/ApplicationsRailList";
import ApplicationsTable from "./components/ApplicationsTable";
import ClosedApplicationsSection from "./components/ClosedApplicationsSection";


const CLOSED_STATUSES = new Set<ApplicationStatus>([
  ApplicationStatus.JOB_CLOSED,
  ApplicationStatus.WITHDRAWN,
]);

const ALL_FILTER = "ALL";
type FilterValue = string;
type AppSortColumn = "name" | "created_at" | "status";
const naturalOrder = (column: AppSortColumn) =>
  column === "created_at" ? "desc" : "asc";

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminApplicationsPage() {
  const { t } = useTranslation(["admin", "md"]);
  usePageTitle(t("admin:applications.title"));
  const toast = useToast();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const selectedId = id != null ? Number(id) : null;

  const [filter, setFilter] = useState<FilterValue>(() => {
    const s = new URLSearchParams(window.location.search).get("status");
    if (
      s === ApplicationStatus.NEW ||
      s === ApplicationStatus.APPROVED_BY_ADMIN ||
      s === ApplicationStatus.REJECTED ||
      s === ApplicationStatus.HIRED ||
      s === ApplicationStatus.WITHDRAWN
    ) {
      return s;
    }
    return ALL_FILTER;
  });

  // Job filter: multi-select (client-side). URL ?job=<id> seeds the array.
  const [jobFilter, setJobFilter] = useState<number[]>(() => {
    const val = new URLSearchParams(window.location.search).get("job");
    return val && !Number.isNaN(Number(val)) ? [Number(val)] : [];
  });

  // Clean URL params on mount after reading them
  useEffect(() => {
    if (jobFilter.length > 0) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redirect to the list when /admin/applications/:id has a non-numeric id.
  useEffect(() => {
    if (id != null && !Number.isFinite(selectedId)) {
      navigate("/admin/applications", { replace: true });
    }
  }, [id, selectedId, navigate]);

  const { chain, click, replace } = useSortChain<AppSortColumn>([
    { column: "status", order: "asc" },
    { column: "created_at", order: "desc" },
  ]);
  const handleSort = (column: AppSortColumn) => click(column, naturalOrder(column));
  const [primary, secondary] = chain;
  const { column: sort, order } = primary;
  const sort2 = secondary?.column;
  const order2 = secondary?.order;
  const columnState = (column: AppSortColumn) => {
    const idx = chain.findIndex((key) => key.column === column);
    if (idx === -1) return { active: false, order: "desc" as const, rank: undefined };
    return {
      active: true,
      order: chain[idx].order,
      rank: chain.length > 1 ? ((idx + 1) as 1 | 2) : undefined,
    };
  };

  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ApplicationWithDetails>> => {
      const params: ApplicationListParams = { cursor, sort, order, sort2, order2 };
      if (filter !== ALL_FILTER) params.status = filter as ApplicationStatus;
      if (debouncedQuery.trim()) params.q = debouncedQuery.trim();
      return getApplications(params);
    },
    [filter, sort, order, sort2, order2, debouncedQuery],
  );

  const {
    items: applications,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    updateItem,
    removeItem,
  } = useInfiniteList<ApplicationWithDetails>(fetcher);

  const [notesModal, setNotesModal] = useState<ApplicationWithDetails | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<ApplicationWithDetails | null>(
    null,
  );
  const [isPendingDelete, setIsPendingDelete] = useState(false);

  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);

  // Cache of all jobs and active companies for the filter selects.
  const [allJobs, setAllJobs] = useState<
    { id: number; title: string; company_id: number }[]
  >([]);
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(
    new Map(),
  );
  const [jobTitleById, setJobTitleById] = useState<Map<number, string>>(new Map());
  useEffect(() => {
    const ctrl = new AbortController();
    getJobs({ limit: 100 }, ctrl.signal)
      .then((jobsPage) => {
        setAllJobs(
          jobsPage.items.map((j) => ({
            id: j.id,
            title: j.title,
            company_id: j.company_id,
          })),
        );
        setJobTitleById(new Map(jobsPage.items.map((j) => [j.id, j.title])));
        setCompanyNameById(
          new Map(jobsPage.items.map((j) => [j.company_id, j.company_name])),
        );
      })
      .catch(() => {
        /* best-effort */
      });
    return () => ctrl.abort();
  }, []);

  const filteredApplications = useMemo(() => {
    const jobSet = new Set(jobFilter);
    const companySet = new Set(companyFilter);
    return applications.filter((a) => {
      if (jobSet.size > 0 && !jobSet.has(a.job_id)) return false;
      if (companySet.size > 0 && !companySet.has(a.job.company_id)) return false;
      return true;
    });
  }, [applications, jobFilter, companyFilter]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) +
    (filter !== ALL_FILTER ? 1 : 0) +
    jobFilter.length +
    companyFilter.length;

  const STATUS_LABELS: Record<string, string> = {
    NEW: t("admin:applications.statusLabels.NEW"),
    APPROVED_BY_ADMIN: t("admin:applications.statusLabels.APPROVED_BY_ADMIN"),
    REJECTED: t("admin:applications.statusLabels.REJECTED"),
    HIRED: t("admin:applications.statusLabels.HIRED"),
    JOB_CLOSED: t("admin:applications.statusLabels.JOB_CLOSED"),
    WITHDRAWN: t("admin:applications.statusLabels.WITHDRAWN"),
  };

  const [activeFiltered, closedFiltered] = useMemo(() => {
    const active: ApplicationWithDetails[] = [];
    const closed: ApplicationWithDetails[] = [];
    for (const a of filteredApplications) {
      if (CLOSED_STATUSES.has(a.status as ApplicationStatus)) closed.push(a);
      else active.push(a);
    }
    return [active, closed];
  }, [filteredApplications]);

  const selectedApplication =
    selectedId != null ? applications.find((a) => a.id === selectedId) : undefined;

  async function handleDeleteConfirm() {
    if (!deleteCandidate) return;
    setIsPendingDelete(true);
    try {
      await deleteApplication(deleteCandidate.id);
      removeItem((a) => a.id === deleteCandidate.id);
      toast.success(t("admin:applications.deletedToast"));
      setDeleteCandidate(null);
      if (selectedId === deleteCandidate.id) {
        navigate("/admin/applications");
      }
    } catch {
      toast.error(t("admin:applications.errors.deleteFailed"));
    } finally {
      setIsPendingDelete(false);
    }
  }

  const dialogs = (
    <>
      <ApplicationNotesDialog
        app={notesModal}
        onClose={() => setNotesModal(null)}
        onSaved={(updated) => {
          updateItem(
            (a) => a.id === updated.id,
            (prev) => ({
              ...prev,
              admin_notes: updated.admin_notes,
              updated_at: updated.updated_at,
            }),
          );
          toast.success(t("admin:applications.notesSavedToast"));
          setNotesModal(null);
        }}
        onError={() => toast.error(t("admin:applications.errors.notesFailed"))}
      />

      <ConfirmDialog
        open={deleteCandidate != null}
        onOpenChange={(o) => !o && setDeleteCandidate(null)}
        title={t("admin:applications.deleteConfirmTitle")}
        message={t("admin:applications.deleteConfirm")}
        confirmLabel={t("admin:applications.deleteConfirmYes")}
        variant="danger"
        isPending={isPendingDelete}
        onConfirm={handleDeleteConfirm}
      />
    </>
  );

  const sortControl = (
    <SortControl
      ariaLabel={t("admin:applications.sort.label")}
      value={`${sort}:${order}`}
      onChange={(col, ord) => replace(col as AppSortColumn, ord)}
      options={[
        { value: "status:desc", label: t("admin:applications.sort.statusDesc") },
        { value: "status:asc", label: t("admin:applications.sort.statusAsc") },
        { value: "created_at:desc", label: t("admin:applications.sort.dateDesc") },
        { value: "created_at:asc", label: t("admin:applications.sort.dateAsc") },
        { value: "name:asc", label: t("admin:applications.sort.nameAsc") },
        { value: "name:desc", label: t("admin:applications.sort.nameDesc") },
      ]}
    />
  );

  const searchAndFilters = (
    <>
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin:applications.searchPlaceholder")}
            isClearable
          />
        </div>
        <button
          type="button"
          onClick={() => setIsFilterOpen((o) => !o)}
          aria-expanded={isFilterOpen}
          aria-label={t("admin:applications.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            isFilterOpen
              ? "border-copper/50 bg-copper/10 text-white"
              : "border-white/15 bg-card-raised/40 text-white/75 hover:border-copper/40 hover:text-white"
          }`}
        >
          <FunnelIcon />
          <span className="hidden sm:inline">{t("admin:applications.filters")}</span>
          {activeFilterCount > 0 && (
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      <ApplicationsFilterPanel
        filterState={{
          filter,
          setFilter,
          query,
          setQuery,
          jobFilter,
          setJobFilter,
          companyFilter,
          setCompanyFilter,
        }}
        lookupMaps={{ allJobs, companyNameById, jobTitleById }}
        uiState={{ activeFilterCount, isFilterOpen, statusLabels: STATUS_LABELS }}
      />
    </>
  );

  if (selectedId == null) {
    return (
      <div>
        <h1 data-page-heading className="sr-only">
          {t("admin:applications.title")}
        </h1>
        <PageHeader
          eyebrow={t("admin:applications.title")}
          subtitle={t("admin:applications.subtitle")}
        />

        {searchAndFilters}

        <ListStateSwitch
          isLoading={isLoading}
          loading={
            <>
              <div className="md:hidden">
                <MobileListSkeleton rows={6} />
              </div>
              <div className="hidden md:block">
                <TableSkeleton rows={6} columns={4} />
              </div>
            </>
          }
          error={error}
          onRetry={reload}
          errorMessage={t("admin:applications.loadError")}
          isEmpty={filteredApplications.length === 0}
          hasQuery={applications.length > 0}
          emptyEyebrow={t("admin:applications.title")}
          emptyHeadline={t("admin:applications.empty")}
        >
          <>
            {/* Mobile */}
            <div className="md:hidden">
              <div className="mb-3">{sortControl}</div>
              <ApplicationsRailList
                applications={activeFiltered}
                selectedId={null}
                statusLabels={STATUS_LABELS}
                statusColors={APPLICATION_STATUS_COLORS}
                onView={(app) => navigate(`/admin/applications/${app.id}`)}
                onEditNotes={setNotesModal}
                onDelete={setDeleteCandidate}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />
            </div>

            {/* Desktop */}
            <ApplicationsTable
              applications={activeFiltered}
              statusLabels={STATUS_LABELS}
              columnState={columnState}
              onSort={handleSort}
              onEditNotes={setNotesModal}
              onDelete={setDeleteCandidate}
            />

            {/* Sentinel for IntersectionObserver */}
            <InfiniteScrollFooter
              sentinelRef={sentinelRef}
              isFetchingMore={isFetchingMore}
            />

            <ClosedApplicationsSection
              apps={closedFiltered}
              statusLabels={STATUS_LABELS}
              statusColors={APPLICATION_STATUS_COLORS}
              onView={(app) => navigate(`/admin/applications/${app.id}`)}
              onEditNotes={setNotesModal}
              onDelete={setDeleteCandidate}
            />
          </>
        </ListStateSwitch>

        {dialogs}
      </div>
    );
  }

  return (
    <SplitPaneLayout
      recordPresent={selectedId != null}
      showListLabel={t("admin:applications.record.showList")}
      hideListLabel={t("admin:applications.record.hideList")}
      rail={
        <>
          <h1 data-page-heading className="sr-only">
            {t("admin:applications.title")}
          </h1>
          <PageHeader
            eyebrow={t("admin:applications.title")}
            subtitle={t("admin:applications.subtitle")}
          />

          {searchAndFilters}

          <div className="mb-3">{sortControl}</div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            <ListStateSwitch
              isLoading={isLoading}
              loading={<MobileListSkeleton rows={6} />}
              error={error}
              onRetry={reload}
              errorMessage={t("admin:applications.loadError")}
              isEmpty={filteredApplications.length === 0}
              hasQuery={applications.length > 0}
              emptyEyebrow={t("admin:applications.title")}
              emptyHeadline={t("admin:applications.empty")}
            >
              <ApplicationsRailList
                applications={filteredApplications}
                selectedId={selectedId}
                statusLabels={STATUS_LABELS}
                statusColors={APPLICATION_STATUS_COLORS}
                onView={(app) => navigate(`/admin/applications/${app.id}`)}
                onEditNotes={setNotesModal}
                onDelete={setDeleteCandidate}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />
            </ListStateSwitch>
          </div>
        </>
      }
      record={
        <ApplicationRecordPane
          applicationId={selectedId}
          application={selectedApplication}
          onUpdated={(patch) =>
            updateItem(
              (a) => a.id === patch.id,
              (prev) => ({ ...prev, ...patch }),
            )
          }
        />
      }
    >
      {dialogs}
    </SplitPaneLayout>
  );
}

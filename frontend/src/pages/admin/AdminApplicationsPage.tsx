import { useCallback, useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import FunnelIcon from "@/components/admin/FunnelIcon";
import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import PageHeader from "@/components/ui/PageHeader";
import SearchInput from "@/components/ui/SearchInput";
import StatusBadge from "@/components/ui/StatusBadge";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { APPLICATION_STATUS_COLORS } from "@/constants/statusColors";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import {
  deleteApplication,
  getApplications,
  type ApplicationListParams,
} from "@/services/adminApplications";
import { getActiveCompanies } from "@/services/adminCompanies";
import { getJobs } from "@/services/adminJobs";
import { type ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

import ApplicationNotesDialog from "./components/ApplicationNotesDialog";
import ApplicationRecordPane from "./components/ApplicationRecordPane";
import ApplicationsFilterPanel from "./components/ApplicationsFilterPanel";
import ApplicationsRailList from "./components/ApplicationsRailList";
import ApplicationStatusDialog from "./components/ApplicationStatusDialog";
import ClosedApplicationsSection from "./components/ClosedApplicationsSection";
import { IconSparkle } from "./components/TriageIcons";


const CLOSED_STATUSES = new Set<ApplicationStatus>([
  ApplicationStatus.JOB_CLOSED,
  ApplicationStatus.WITHDRAWN,
]);

const ALL_FILTER = "ALL";
type FilterValue = string;

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

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ApplicationWithDetails>> => {
      const params: ApplicationListParams = { cursor };
      if (filter !== ALL_FILTER) params.status = filter as ApplicationStatus;
      return getApplications(params);
    },
    [filter],
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

  const [statusModal, setStatusModal] = useState<ApplicationWithDetails | null>(null);
  const [notesModal, setNotesModal] = useState<ApplicationWithDetails | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<ApplicationWithDetails | null>(
    null,
  );
  const [isPendingDelete, setIsPendingDelete] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);

  // Client-side filters (status is server-side via fetcher).
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
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
    Promise.all([
      getJobs({ limit: 100 }, ctrl.signal),
      getActiveCompanies({ limit: 100 }, ctrl.signal),
    ])
      .then(([jobsPage, companiesPage]) => {
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
      })
      .catch(() => {
        /* best-effort */
      });
    return () => ctrl.abort();
  }, []);

  const filteredApplications = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    const jobSet = new Set(jobFilter);
    const companySet = new Set(companyFilter);
    return applications.filter((a) => {
      if (jobSet.size > 0 && !jobSet.has(a.job_id)) return false;
      if (companySet.size > 0 && !companySet.has(a.job.company_id)) return false;
      if (!q) return true;
      return [
        a.candidate.full_name,
        a.candidate.email,
        a.candidate.phone ?? "",
        a.job.title,
        a.job.location,
        a.admin_notes ?? "",
      ].some((s) => s.toLowerCase().includes(q));
    });
  }, [applications, debouncedQuery, jobFilter, companyFilter]);

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
      <ApplicationStatusDialog
        app={statusModal}
        onClose={() => setStatusModal(null)}
        onSaved={(updated) => {
          updateItem(
            (a) => a.id === updated.id,
            (prev) => ({
              ...prev,
              status: updated.status,
              admin_notes: updated.admin_notes,
              updated_at: updated.updated_at,
            }),
          );
          toast.success(t("admin:applications.savedToast"));
          setStatusModal(null);
        }}
        onError={() => toast.error(t("admin:applications.errors.updateFailed"))}
      />

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
          action={
            <Button onClick={() => navigate("/admin/applications/triage")}>
              <IconSparkle className="ms-0 me-1.5 size-3.5" />
              {t("admin:applications.triage.entryButton")}
            </Button>
          }
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
            {/* Mobile — same rail rows as the split-pane workspace; tap navigates straight to the record route, matching Candidates */}
            <div className="md:hidden">
              <ApplicationsRailList
                applications={activeFiltered}
                selectedId={null}
                statusLabels={STATUS_LABELS}
                statusColors={APPLICATION_STATUS_COLORS}
                onView={(app) => navigate(`/admin/applications/${app.id}`)}
                onUpdateStatus={setStatusModal}
                onEditNotes={setNotesModal}
                onDelete={setDeleteCandidate}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />
            </div>

            {/* Desktop */}
            <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
              <table className="min-w-full divide-y divide-white/6 text-sm">
                <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                  <tr>
                    <th className="px-4 py-3 text-start">
                      {t("admin:applications.table.candidate")}
                    </th>
                    <th className="px-4 py-3 text-start">
                      {t("admin:applications.table.job")}
                    </th>
                    <th className="px-4 py-3 text-start">
                      {t("admin:applications.table.status")}
                    </th>
                    <th className="px-4 py-3 text-start">
                      {t("admin:applications.table.date")}
                    </th>
                    <th className="px-4 py-3 text-end" aria-hidden />
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/6">
                  {activeFiltered.map((app) => (
                    <tr
                      key={app.id}
                      onClick={() => navigate(`/admin/applications/${app.id}`)}
                      className="cursor-pointer transition hover:bg-white/3"
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-white/85">
                          {app.candidate.full_name}
                        </p>
                        <p className="text-xs text-white/40">{app.candidate.email}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-white/80">{app.job.title}</p>
                        <p className="text-xs text-white/40">{app.job.location}</p>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          label={STATUS_LABELS[app.status]}
                          colorCls={APPLICATION_STATUS_COLORS[app.status]}
                        />
                      </td>
                      <td className="px-4 py-3 text-white/40">
                        {formatDate(app.created_at)}
                      </td>
                      <td
                        className="px-4 py-3 text-end"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <DropdownMenu
                          ariaLabel={t("admin:applications.rowActionsLabel")}
                          trigger={<KebabButton size="sm" />}
                        >
                          <DropdownMenuItem
                            onSelect={() => navigate(`/admin/applications/${app.id}`)}
                          >
                            {t("admin:applications.viewAction")}
                          </DropdownMenuItem>
                          {app.status !== ApplicationStatus.WITHDRAWN && (
                            <DropdownMenuItem onSelect={() => setStatusModal(app)}>
                              {t("admin:applications.updateStatusAction")}
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem onSelect={() => setNotesModal(app)}>
                            {t("admin:applications.editNotesAction")}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant="danger"
                            onSelect={() => setDeleteCandidate(app)}
                          >
                            {t("admin:applications.deleteAction")}
                          </DropdownMenuItem>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

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
              onUpdateStatus={setStatusModal}
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
      collapsed={railCollapsed}
      onToggleCollapsed={() => setRailCollapsed((v) => !v)}
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
                onUpdateStatus={setStatusModal}
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

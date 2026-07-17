import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import FunnelIcon from "@/components/admin/FunnelIcon";
import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SearchableSelect from "@/components/admin/SearchableSelect";
import SortControl from "@/components/admin/SortControl";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import PageHeader from "@/components/ui/PageHeader";
import SearchInput from "@/components/ui/SearchInput";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useColumnSort } from "@/hooks/useColumnSort";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { deleteCandidate, getCandidates } from "@/services/adminCandidates";
import { getJobs } from "@/services/adminJobs";
import type { CandidateAdminRead } from "@/types/candidates";
import type { JobRead } from "@/types/jobs";

import CandidateRecordPane from "./components/CandidateRecordPane";
import CandidatesFilterPanel from "./components/CandidatesFilterPanel";
import CandidatesRailList from "./components/CandidatesRailList";
import CandidatesTable from "./components/CandidatesTable";

export default function AdminCandidatesPage() {
  const { t } = useTranslation(["admin", "common", "md"]);
  usePageTitle(t("admin:candidates.title"));
  const toast = useToast();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const selectedId = id != null ? Number(id) : null;

  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);

  const { sort, order, toggle } = useColumnSort<"name" | "created_at">({
    column: "created_at",
    order: "desc",
  });
  const handleSort = (column: "name" | "created_at") =>
    toggle(column, column === "name" ? "asc" : "desc");

  // AI score sort
  const [scoreSort, setScoreSort] = useState(false);
  const [scoreSortJobId, setScoreSortJobId] = useState<number | null>(null);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [jobs, setJobs] = useState<Pick<JobRead, "id" | "title">[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    getJobs({ limit: 100 }, ctrl.signal)
      .then((page) => setJobs(page.items.map((j) => ({ id: j.id, title: j.title }))))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<CandidateAdminRead>> => {
      if (scoreSort && scoreSortJobId != null) {
        return getCandidates({
          q: debouncedQuery.trim() || undefined,
          sort: "score",
          job_id: scoreSortJobId,
          include_deleted: includeDeleted || undefined,
        });
      }
      return getCandidates({
        cursor,
        q: debouncedQuery.trim() || undefined,
        sort,
        order,
        include_deleted: includeDeleted || undefined,
      });
    },
    [debouncedQuery, sort, order, scoreSort, scoreSortJobId, includeDeleted],
  );

  const {
    items: candidates,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    removeItem,
  } = useInfiniteList<CandidateAdminRead>(fetcher);

  const [deletePending, setDeletePending] = useState<CandidateAdminRead | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);

  useEffect(() => {
    if (id != null && !Number.isFinite(selectedId)) {
      navigate("/admin/candidates", { replace: true });
    }
  }, [id, selectedId, navigate]);

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setPendingDelete(true);
    try {
      await deleteCandidate(deletePending.id);
      removeItem((c) => c.id === deletePending.id);
      toast.success(t("admin:candidates.deletedToast"));
      setDeletePending(null);
      if (selectedId === deletePending.id) {
        navigate("/admin/candidates");
      }
    } catch (err) {
      const isAlreadyDeleted =
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        (err as { response?: { status?: number } }).response?.status === 409;
      toast.error(
        isAlreadyDeleted
          ? t("admin:candidates.errors.alreadyDeleted")
          : t("admin:candidates.errors.deleteFailed"),
      );
    } finally {
      setPendingDelete(false);
    }
  }

  const selectedCandidate =
    selectedId != null ? candidates.find((c) => c.id === selectedId) : undefined;

  const dialogs = (
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
  );

  const activeFilterCount = (debouncedQuery.trim() ? 1 : 0) + (includeDeleted ? 1 : 0);

  const header = (
    <>
      <h1 data-page-heading className="sr-only">
        {t("admin:candidates.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin:candidates.title")}
        subtitle={t("admin:candidates.subtitle")}
      />
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin:candidates.searchPlaceholder")}
            isClearable
          />
        </div>
        <button
          type="button"
          onClick={() => setIsFilterOpen((o) => !o)}
          aria-expanded={isFilterOpen}
          aria-label={t("admin:candidates.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            isFilterOpen
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

      <CandidatesFilterPanel
        isFilterOpen={isFilterOpen}
        activeFilterCount={activeFilterCount}
        query={query}
        setQuery={setQuery}
        includeDeleted={includeDeleted}
        setIncludeDeleted={setIncludeDeleted}
      />
    </>
  );

  const listStateProps = {
    isLoading,
    error,
    onRetry: reload,
    errorMessage: t("admin:candidates.loadError"),
    isEmpty: candidates.length === 0,
    hasQuery: Boolean(debouncedQuery.trim()),
    emptyEyebrow: t("admin:candidates.title"),
    emptyHeadline: t("admin:candidates.empty"),
    noResultsMessage: t("admin:candidates.noResults"),
    // Searching for someone who deleted their account otherwise looks identical to
    // "no such candidate" — the row is there, just filtered out by default.
    emptyDescription: includeDeleted
      ? undefined
      : t("admin:candidates.emptyDeletedHint"),
    emptyAction: includeDeleted ? undefined : (
      <Button variant="ghost" size="sm" onClick={() => setIncludeDeleted(true)}>
        {t("admin:candidates.showDeletedToggle")}
      </Button>
    ),
  };

  function withListState(loading: ReactNode, children: ReactNode) {
    return (
      <ListStateSwitch {...listStateProps} loading={loading}>
        {children}
      </ListStateSwitch>
    );
  }

  const jobOptions = jobs.map((j) => ({ value: j.id, label: j.title }));

  // `sortWrapperCls` lets the full-list view drop the sort dropdown on desktop,
  // where CandidatesTable's own sortable column headers already cover it (the
  // jobs and applications pages gate it the same way). The rail keeps it at
  // every width — it has no column headers to fall back on.
  const renderAiSortPanel = (sortWrapperCls: string) => (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => {
          setScoreSort((s) => !s);
          if (scoreSort) setScoreSortJobId(null);
        }}
        className={[
          "ai-sort-btn inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-all duration-200",
          scoreSort
            ? "ai-sort-btn--active border-copper/50 bg-copper/10 text-copper"
            : "border-white/12 bg-card-raised/40 text-white/50 hover:border-copper/30 hover:bg-copper/5 hover:text-white/80",
        ].join(" ")}
        aria-pressed={scoreSort}
      >
        <SparkleIcon active={scoreSort} />
        {t("admin:candidates.sort.aiScore")}
      </button>

      {scoreSort && (
        <div className="min-w-0 flex-1 animate-[ai-dropdown-in_0.18s_ease-out_both]">
          <SearchableSelect
            value={scoreSortJobId}
            onChange={setScoreSortJobId}
            options={jobOptions}
            placeholder={t("admin:candidates.sort.selectJob")}
            searchPlaceholder={t("admin:candidates.sort.searchJob")}
          />
        </div>
      )}

      {!scoreSort && (
        <div className={sortWrapperCls}>
          <SortControl
            ariaLabel={t("admin:candidates.sort.label")}
            value={`${sort}:${order}`}
            onChange={(col, ord) => toggle(col as "name" | "created_at", ord)}
            options={[
              { value: "created_at:desc", label: t("admin:candidates.sort.dateDesc") },
              { value: "created_at:asc", label: t("admin:candidates.sort.dateAsc") },
              { value: "name:asc", label: t("admin:candidates.sort.nameAsc") },
              { value: "name:desc", label: t("admin:candidates.sort.nameDesc") },
            ]}
          />
        </div>
      )}
    </div>
  );

  const showScore = scoreSort && scoreSortJobId != null;

  if (selectedId == null) {
    return (
      <div>
        {header}
        {renderAiSortPanel("w-full md:hidden")}
        {withListState(
          <>
            <div className="md:hidden">
              <MobileListSkeleton rows={6} />
            </div>
            <div className="hidden md:block">
              <TableSkeleton rows={6} columns={6} />
            </div>
          </>,
          <>
            <div className="md:hidden">
              <CandidatesRailList
                candidates={candidates}
                showScore={showScore}
                onView={(c) => navigate(`/admin/candidates/${c.id}`)}
                onDelete={setDeletePending}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />
            </div>

            <CandidatesTable
              candidates={candidates}
              sort={sort}
              order={order}
              showScore={showScore}
              onSort={handleSort}
              onView={(c) => navigate(`/admin/candidates/${c.id}`)}
              onDelete={setDeletePending}
              sentinelRef={sentinelRef}
              isFetchingMore={isFetchingMore}
            />
          </>,
        )}
        {dialogs}
      </div>
    );
  }

  return (
    <SplitPaneLayout
      recordPresent={selectedId != null}
      showListLabel={t("admin:candidates.record.showList")}
      hideListLabel={t("admin:candidates.record.hideList")}
      rail={
        <>
          {header}
          {renderAiSortPanel("w-full")}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {withListState(
              <MobileListSkeleton rows={6} />,
              <CandidatesRailList
                candidates={candidates}
                selectedId={selectedId}
                showScore={showScore}
                onView={(c) => navigate(`/admin/candidates/${c.id}`)}
                onDelete={setDeletePending}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />,
            )}
          </div>
        </>
      }
      record={
        <CandidateRecordPane
          candidateId={selectedId}
          candidate={selectedCandidate}
          onDeleted={(deletedId) => removeItem((c) => c.id === deletedId)}
        />
      }
    >
      {dialogs}
    </SplitPaneLayout>
  );
}

function SparkleIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`size-3.5 shrink-0 ${active ? "ai-sparkle-active" : ""}`}
      aria-hidden="true"
    >
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.22 3.22l1.42 1.42M11.36 11.36l1.42 1.42M11.36 4.64l-1.42 1.42M4.64 11.36l-1.42 1.42" />
    </svg>
  );
}

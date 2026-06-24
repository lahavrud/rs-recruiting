import { useCallback, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

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
import { deleteCandidate, getCandidates } from "@/services/adminCandidates";
import type { CandidateProfileRead } from "@/types/candidates";

import CandidateRecordPane from "./components/CandidateRecordPane";
import CandidatesRailList from "./components/CandidatesRailList";
import CandidatesTable from "./components/CandidatesTable";
import RailToggleIcon from "./components/RailToggleIcon";

export default function AdminCandidatesPage() {
  const { t } = useTranslation(['admin', 'common', 'md']);
  usePageTitle(t("admin:candidates.title"));
  const toast = useToast();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const selectedId = id != null ? Number(id) : null;

  // Search re-fetches from the server (debounced), resetting the cursor —
  // matching against already-loaded items only would miss candidates
  // further down the (cursor-paginated) list.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<CandidateProfileRead>> =>
      getCandidates({ cursor, q: debouncedQuery.trim() || undefined }),
    [debouncedQuery],
  );

  const {
    items: candidates,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    removeItem,
  } = useInfiniteList<CandidateProfileRead>(fetcher);

  const [deletePending, setDeletePending] = useState<CandidateProfileRead | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);

  // Redirect to the list when /admin/candidates/:id has a non-numeric id.
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
    } catch {
      toast.error(t("admin:candidates.errors.deleteFailed"));
    } finally {
      setPendingDelete(false);
    }
  }

  const selectedCandidate =
    selectedId != null ? candidates.find((c) => c.id === selectedId) : undefined;

  const dialogs = (
    <>
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
    </>
  );

  if (selectedId == null) {
    return (
      <div>
        <h1 data-page-heading className="sr-only">
          {t("admin:candidates.title")}
        </h1>
        <PageHeader
          eyebrow={t("admin:candidates.title")}
          subtitle={t("admin:candidates.subtitle")}
        />

        {/* Search */}
        <div className="mb-3">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin:candidates.searchPlaceholder")}
            isClearable
          />
        </div>

        {isLoading ? (
          <>
            <div className="md:hidden">
              <MobileListSkeleton rows={6} />
            </div>
            <div className="hidden md:block">
              <TableSkeleton rows={6} columns={6} />
            </div>
          </>
        ) : error ? (
          <ErrorState message={t("admin:candidates.loadError")} onRetry={reload} />
        ) : candidates.length === 0 ? (
          debouncedQuery.trim() ? (
            <NoResults />
          ) : (
            <EmptyState
              eyebrow={t("admin:candidates.title")}
              headline={t("admin:candidates.empty")}
            />
          )
        ) : (
          <>
            <div className="md:hidden">
              <CandidatesRailList
                candidates={candidates}
                onView={(c) => navigate(`/admin/candidates/${c.id}`)}
                onDelete={setDeletePending}
                sentinelRef={sentinelRef}
                isFetchingMore={isFetchingMore}
              />
            </div>

            <CandidatesTable
              candidates={candidates}
              onView={(c) => navigate(`/admin/candidates/${c.id}`)}
              onDelete={setDeletePending}
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
    <div className="relative flex h-full min-h-0 flex-col md:flex-row">
      <div
        className={`hidden min-h-0 flex-col overflow-hidden transition-[width,opacity,margin] duration-300 ease-in-out md:flex md:flex-none ${
          railCollapsed
            ? "md:me-0 md:w-0 md:opacity-0"
            : "md:me-6 md:w-[360px] md:opacity-100"
        }`}
      >
        <h1 data-page-heading className="sr-only">
          {t("admin:candidates.title")}
        </h1>
        <PageHeader
          eyebrow={t("admin:candidates.title")}
          subtitle={t("admin:candidates.subtitle")}
        />

        {/* Search */}
        <div className="mb-3">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin:candidates.searchPlaceholder")}
            isClearable
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {isLoading ? (
            <MobileListSkeleton rows={6} />
          ) : error ? (
            <ErrorState message={t("admin:candidates.loadError")} onRetry={reload} />
          ) : candidates.length === 0 ? (
            debouncedQuery.trim() ? (
              <NoResults />
            ) : (
              <EmptyState
                eyebrow={t("admin:candidates.title")}
                headline={t("admin:candidates.empty")}
              />
            )
          ) : (
            <CandidatesRailList
              candidates={candidates}
              selectedId={selectedId}
              onView={(c) => navigate(`/admin/candidates/${c.id}`)}
              onDelete={setDeletePending}
              sentinelRef={sentinelRef}
              isFetchingMore={isFetchingMore}
            />
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto md:min-w-0">
        <CandidateRecordPane
          candidateId={selectedId}
          candidate={selectedCandidate}
          onDeleted={(deletedId) => removeItem((c) => c.id === deletedId)}
        />
      </div>

      <button
        type="button"
        onClick={() => setRailCollapsed((v) => !v)}
        aria-label={t(
          railCollapsed ? "admin:candidates.record.showList" : "admin:candidates.record.hideList",
        )}
        title={t(
          railCollapsed ? "admin:candidates.record.showList" : "admin:candidates.record.hideList",
        )}
        className={`absolute top-1/2 z-20 hidden size-9 -translate-y-1/2 translate-x-1/2 items-center justify-center rounded-full border border-white/10 bg-card-raised text-white/40 transition-all duration-300 ease-in-out hover:border-copper/30 hover:text-copper md:flex ${
          railCollapsed ? "start-0" : "start-[384px]"
        }`}
      >
        <RailToggleIcon className="size-4" flipped={railCollapsed} />
      </button>

      {dialogs}
    </div>
  );
}

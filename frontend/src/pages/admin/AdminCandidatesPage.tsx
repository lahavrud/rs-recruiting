import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
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

  const header = (
    <>
      <h1 data-page-heading className="sr-only">
        {t("admin:candidates.title")}
      </h1>
      <PageHeader eyebrow={t("admin:candidates.title")} subtitle={t("admin:candidates.subtitle")} />
      <div className="mb-3">
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder={t("admin:candidates.searchPlaceholder")}
          isClearable
        />
      </div>
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
  };

  function withListState(loading: ReactNode, children: ReactNode) {
    return (
      <ListStateSwitch {...listStateProps} loading={loading}>
        {children}
      </ListStateSwitch>
    );
  }

  if (selectedId == null) {
    return (
      <div>
        {header}
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
          </>,
        )}
        {dialogs}
      </div>
    );
  }

  return (
    <SplitPaneLayout
      collapsed={railCollapsed}
      onToggleCollapsed={() => setRailCollapsed((v) => !v)}
      showListLabel={t("admin:candidates.record.showList")}
      hideListLabel={t("admin:candidates.record.hideList")}
      rail={
        <>
          {header}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {withListState(
              <MobileListSkeleton rows={6} />,
              <CandidatesRailList
                candidates={candidates}
                selectedId={selectedId}
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

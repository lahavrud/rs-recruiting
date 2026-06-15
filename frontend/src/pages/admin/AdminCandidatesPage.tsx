import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { deleteCandidate, getCandidates } from "@/services/adminCandidates";
import type { CandidateProfileRead } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SearchInput from "@/components/ui/SearchInput";
import NoResults from "@/components/ui/NoResults";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import CandidateEditDialog from "./components/CandidateEditDialog";
import CandidateRecordPane from "./components/CandidateRecordPane";
import CandidatesRailList from "./components/CandidatesRailList";
import RailToggleIcon from "./components/RailToggleIcon";

export default function AdminCandidatesPage() {
  const { t } = useTranslation(['admin', 'common', 'md']);
  usePageTitle(t("admin:candidates.title"));
  const toast = useToast();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const selectedId = id != null ? Number(id) : null;

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

  const [editing, setEditing] = useState<CandidateProfileRead | null>(null);
  const [deletePending, setDeletePending] = useState<CandidateProfileRead | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);

  // Client-side search on the loaded candidate set.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);

  const filteredCandidates = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((c) =>
      [c.full_name, c.email, c.phone ?? "", c.linkedin_url ?? ""].some((s) =>
        s.toLowerCase().includes(q),
      ),
    );
  }, [candidates, debouncedQuery]);

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

  return (
    <div className="relative flex h-full min-h-0 flex-col md:flex-row">
      <div
        className={
          selectedId != null
            ? `hidden min-h-0 flex-col overflow-hidden transition-[width,opacity,margin] duration-300 ease-in-out md:flex md:flex-none ${
                railCollapsed
                  ? "md:me-0 md:w-0 md:opacity-0"
                  : "md:me-6 md:w-[360px] md:opacity-100"
              }`
            : "flex min-h-0 flex-1 flex-col md:me-6 md:w-[360px] md:flex-none"
        }
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
            clearable
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {isLoading ? (
            <MobileListSkeleton rows={6} />
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
            <CandidatesRailList
              candidates={filteredCandidates}
              selectedId={selectedId}
              onView={(c) => navigate(`/admin/candidates/${c.id}`)}
              onEdit={setEditing}
              onDelete={setDeletePending}
              sentinelRef={sentinelRef}
              isFetchingMore={isFetchingMore}
            />
          )}
        </div>
      </div>

      <div
        className={
          selectedId == null
            ? "hidden md:block md:min-h-0 md:min-w-0 md:flex-1 md:overflow-y-auto"
            : "min-h-0 flex-1 overflow-y-auto md:min-w-0"
        }
      >
        <CandidateRecordPane
          candidateId={selectedId}
          candidate={selectedCandidate}
          onDeleted={(deletedId) => removeItem((c) => c.id === deletedId)}
        />
      </div>

      {selectedId != null && (
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
      )}

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

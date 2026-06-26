import { useCallback, useEffect, useRef, useState } from "react";

import { useTranslation } from "react-i18next";

import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useToast } from "@/hooks/useToast";
import { getApplications, updateApplicationStatus } from "@/services/adminApplications";
import { type ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

import ApplicationRecordPane from "./ApplicationRecordPane";

interface PendingUndo {
  appId: number;
  label: string;
  timeoutId: number;
}

function AppQueueItem({
  app,
  isSelected,
  onSelect,
}: {
  app: ApplicationWithDetails;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation("admin");
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border p-3 text-start transition ${
        isSelected
          ? "border-copper/40 bg-copper/8"
          : "border-white/6 bg-card hover:border-white/12 hover:bg-card-raised"
      }`}
      aria-pressed={isSelected}
    >
      <p className="truncate font-medium text-white/90">{app.candidate.full_name}</p>
      <p className="mt-0.5 truncate text-xs text-white/50">
        {app.job.title} · {app.job.company_name}
      </p>
      <p className="mt-0.5 text-xs text-white/30">{formatDate(app.created_at)}</p>
      {isSelected && (
        <p className="mt-2 text-[10px] font-medium text-copper/70">
          {t("admin:reviewQueue.keyboard.hint")}
        </p>
      )}
    </button>
  );
}

export default function ApplicationsQueue() {
  const { t } = useTranslation(["admin", "common"]);
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [pendingUndo, setPendingUndo] = useState<PendingUndo | null>(null);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ApplicationWithDetails>> =>
      getApplications({
        cursor,
        status: ApplicationStatus.NEW,
        sort: "created_at",
        order: "asc",
      }),
    [],
  );

  const { items, isLoading, error, reload, sentinelRef, isFetchingMore, removeItem } =
    useInfiniteList<ApplicationWithDetails>(fetcher);

  const selectedItem = selectedId != null ? items.find((a) => a.id === selectedId) : undefined;

  const itemsRef = useRef(items);
  const selectedIdRef = useRef(selectedId);
  useEffect(() => { itemsRef.current = items; }, [items]);
  useEffect(() => { selectedIdRef.current = selectedId; }, [selectedId]);

  const pendingUndoRef = useRef(pendingUndo);
  useEffect(() => { pendingUndoRef.current = pendingUndo; }, [pendingUndo]);

  const decide = useCallback(
    async (
      appId: number,
      status: ApplicationStatus.APPROVED_BY_ADMIN | ApplicationStatus.REJECTED,
    ) => {
      const current = itemsRef.current;
      const idx = current.findIndex((a) => a.id === appId);
      const next = current[idx + 1] ?? current[idx - 1] ?? null;

      removeItem((a) => a.id === appId);
      setSelectedId(next?.id ?? null);

      const prev = pendingUndoRef.current;
      if (prev) {
        window.clearTimeout(prev.timeoutId);
        setPendingUndo(null);
      }

      try {
        await updateApplicationStatus(appId, { status });
        const label =
          status === ApplicationStatus.APPROVED_BY_ADMIN
            ? t("admin:reviewQueue.approved")
            : t("admin:reviewQueue.rejected");
        const timeoutId = window.setTimeout(
          () => setPendingUndo((p) => (p?.appId === appId ? null : p)),
          5000,
        );
        setPendingUndo({ appId, label, timeoutId });
      } catch {
        reload();
        toast.error(
          status === ApplicationStatus.APPROVED_BY_ADMIN
            ? t("admin:reviewQueue.errors.approveFailed")
            : t("admin:reviewQueue.errors.rejectFailed"),
        );
      }
    },
    [removeItem, reload, toast, t],
  );

  async function handleUndo() {
    const undo = pendingUndoRef.current;
    if (!undo) return;
    window.clearTimeout(undo.timeoutId);
    setPendingUndo(null);
    try {
      await updateApplicationStatus(undo.appId, { status: ApplicationStatus.NEW });
      reload();
    } catch {
      toast.error(t("admin:reviewQueue.errors.undoFailed"));
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (target.isContentEditable) return;
      const id = selectedIdRef.current;
      if (id == null) return;
      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        void decide(id, ApplicationStatus.APPROVED_BY_ADMIN);
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        void decide(id, ApplicationStatus.REJECTED);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [decide]);

  const rail = (
    <>
      {pendingUndo && (
        <div className="mb-2 flex items-center justify-between rounded-md border border-copper/20 bg-copper/10 px-3 py-2">
          <span className="text-sm text-white/70">{pendingUndo.label}</span>
          <button
            type="button"
            onClick={() => void handleUndo()}
            className="text-xs font-medium text-copper transition hover:text-gold"
          >
            {t("admin:reviewQueue.undo")}
          </button>
        </div>
      )}

      <ListStateSwitch
        isLoading={isLoading}
        loading={<MobileListSkeleton rows={5} />}
        error={error}
        onRetry={reload}
        errorMessage={t("admin:applications.loadError")}
        isEmpty={items.length === 0}
        hasQuery={false}
        emptyEyebrow={t("admin:reviewQueue.tabs.applications")}
        emptyHeadline={t("admin:reviewQueue.empty.applications")}
      >
        <div className="space-y-1.5">
          {items.map((app) => (
            <AppQueueItem
              key={app.id}
              app={app}
              isSelected={app.id === selectedId}
              onSelect={() => setSelectedId(app.id)}
            />
          ))}
          <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
        </div>
      </ListStateSwitch>
    </>
  );

  return (
    <SplitPaneLayout
      collapsed={railCollapsed}
      onToggleCollapsed={() => setRailCollapsed((v) => !v)}
      showListLabel={t("admin:reviewQueue.record.showList")}
      hideListLabel={t("admin:reviewQueue.record.hideList")}
      rail={rail}
      record={
        <ApplicationRecordPane
          applicationId={selectedId}
          application={selectedItem}
          onUpdated={(patch) => {
            if (
              patch.status != null &&
              patch.status !== ApplicationStatus.NEW
            ) {
              const idx = items.findIndex((a) => a.id === patch.id);
              const next = items[idx + 1] ?? items[idx - 1] ?? null;
              removeItem((a) => a.id === patch.id);
              setSelectedId(next?.id ?? null);
            }
          }}
        />
      }
    />
  );
}

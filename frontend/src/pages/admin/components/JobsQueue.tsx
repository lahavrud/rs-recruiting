import { useCallback, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useToast } from "@/hooks/useToast";
import { approveJob, getJobs, rejectJob } from "@/services/adminJobs";
import type { JobRead } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

import JobRecordPane from "./JobRecordPane";

function JobQueueItem({
  job,
  isSelected,
  onSelect,
}: {
  job: JobRead;
  isSelected: boolean;
  onSelect: () => void;
}) {
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
      <p className="truncate font-medium text-white/90">{job.title}</p>
      <p className="mt-0.5 truncate text-xs text-white/50">{job.company_name}</p>
      <p className="mt-0.5 text-xs text-white/30">{formatDate(job.created_at)}</p>
    </button>
  );
}

export default function JobsQueue() {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<JobRead>> =>
      getJobs({ cursor, status: "PENDING_APPROVAL", sort: "created_at", order: "asc" }),
    [],
  );

  const { items, isLoading, error, reload, sentinelRef, isFetchingMore, removeItem } =
    useInfiniteList<JobRead>(fetcher);

  const selectedItem = selectedId != null ? items.find((j) => j.id === selectedId) : undefined;

  const companyNameById = useMemo(
    () => new Map(items.map((j) => [j.company_id, j.company_name])),
    [items],
  );

  function advance(jobId: number) {
    const idx = items.findIndex((j) => j.id === jobId);
    const next = items[idx + 1] ?? items[idx - 1] ?? null;
    removeItem((j) => j.id === jobId);
    setSelectedId(next?.id ?? null);
  }

  async function handleApprove(job: JobRead) {
    advance(job.id);
    try {
      await approveJob(job.id);
    } catch {
      reload();
      toast.error(t("admin:reviewQueue.errors.approveFailed"));
    }
  }

  async function handleReject(job: JobRead) {
    advance(job.id);
    try {
      await rejectJob(job.id);
    } catch {
      reload();
      toast.error(t("admin:reviewQueue.errors.rejectFailed"));
    }
  }

  const queueList = (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <ListStateSwitch
        isLoading={isLoading}
        loading={<MobileListSkeleton rows={5} />}
        error={error}
        onRetry={reload}
        errorMessage={t("admin:jobs.loadError")}
        isEmpty={items.length === 0}
        hasQuery={false}
        emptyEyebrow={t("admin:reviewQueue.tabs.jobs")}
        emptyHeadline={t("admin:reviewQueue.empty.jobs")}
      >
        <div className="space-y-1.5">
          {items.map((job) => (
            <JobQueueItem
              key={job.id}
              job={job}
              isSelected={job.id === selectedId}
              onSelect={() => setSelectedId(job.id)}
            />
          ))}
          <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
        </div>
      </ListStateSwitch>
    </div>
  );

  const recordPane = (
    <JobRecordPane
      jobId={selectedId}
      job={selectedItem}
      companyNameById={companyNameById}
      onApprove={(job) => void handleApprove(job)}
      onReject={(job) => void handleReject(job)}
      onEdit={(job) => navigate(`/admin/jobs/${job.id}`)}
      onDelete={(job) => navigate(`/admin/jobs/${job.id}`)}
    />
  );

  return (
    <>
      {selectedId == null ? (
        <div className="flex min-h-0 flex-1 flex-col md:hidden">{queueList}</div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col md:hidden">
          <button
            type="button"
            onClick={() => setSelectedId(null)}
            className="mb-3 text-start text-sm text-copper"
          >
            {t("admin:reviewQueue.record.showList")}
          </button>
          <div className="min-h-0 flex-1 overflow-y-auto">{recordPane}</div>
        </div>
      )}
      <div className="hidden min-h-0 flex-1 flex-col md:flex">
        <SplitPaneLayout
          recordPresent={selectedId != null}
          showListLabel={t("admin:reviewQueue.record.showList")}
          hideListLabel={t("admin:reviewQueue.record.hideList")}
          rail={queueList}
          record={recordPane}
        />
      </div>
    </>
  );
}

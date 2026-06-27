import { useCallback, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import JobForm from "@/pages/company/components/JobForm";
import { EMPTY_FORM, emptyRequirements } from "@/pages/company/components/JobFormUtils";
import JobKanban from "@/pages/company/components/JobKanban";
import JobRecommendations from "@/pages/company/components/JobRecommendations";
import {
  createJob,
  deleteJob,
  getCompanyJobs,
  updateJob,
} from "@/services/companyJobs";
import { errorAlertBaseCls } from "@/styles/forms";
import { JobStatus } from "@/types/enums";
import type { JobCreate, JobRead, JobUpdate } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

// ─── Job detail tabs ──────────────────────────────────────────────────────────

type DetailTab = "kanban" | "ai";

interface JobDetailPanelProps {
  job: JobRead;
  onEdit: () => void;
  onDelete: () => void;
  isDeleting: boolean;
  editingDisabled: boolean;
}

function JobDetailPanel({
  job,
  onEdit,
  onDelete,
  isDeleting,
  editingDisabled,
}: JobDetailPanelProps) {
  const { t } = useTranslation("company");
  const [tab, setTab] = useState<DetailTab>("kanban");

  const canEdit =
    job.status === JobStatus.PENDING_APPROVAL || job.status === JobStatus.PUBLISHED;
  const canDelete = job.status === JobStatus.PENDING_APPROVAL;

  const STATUS_LABEL: Record<string, string> = {
    PENDING_APPROVAL: t("company:jobs.statusLabels.PENDING_APPROVAL"),
    PUBLISHED: t("company:jobs.statusLabels.PUBLISHED"),
    CLOSED: t("company:jobs.statusLabels.CLOSED"),
  };
  const STATUS_COLOR: Record<string, string> = {
    PENDING_APPROVAL: "bg-warning/10 text-warning",
    PUBLISHED: "bg-success/10 text-success",
    CLOSED: "bg-white/8 text-white/40",
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-white/90">{job.title}</h2>
            <StatusBadge
              label={STATUS_LABEL[job.status]}
              colorCls={STATUS_COLOR[job.status]}
            />
          </div>
          <p className="mt-0.5 text-sm text-white/45">{job.location}</p>
          <p className="mt-0.5 text-xs text-white/25">
            {t("company:jobs.postedLabel")} {formatDate(job.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          {canEdit && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onEdit}
              disabled={editingDisabled}
            >
              {t("company:jobs.edit")}
            </Button>
          )}
          {canDelete && (
            <Button
              variant="danger"
              size="sm"
              onClick={onDelete}
              disabled={isDeleting || editingDisabled}
            >
              {isDeleting ? "…" : t("company:jobs.delete")}
            </Button>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-white/8 pb-0">
        {(["kanban", "ai"] as DetailTab[]).map((t_) => (
          <button
            key={t_}
            type="button"
            onClick={() => setTab(t_)}
            className={`px-3 py-2 text-sm transition ${
              tab === t_
                ? "border-b-2 border-copper font-medium text-copper"
                : "text-white/40 hover:text-white/70"
            }`}
          >
            {t_ === "kanban"
              ? t("company:jobs.kanban.title")
              : t("company:jobs.kanban.aiTitle")}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="pt-1">
        {tab === "kanban" ? (
          <JobKanban key={job.id} jobId={job.id} />
        ) : (
          <div>
            <p className="mb-3 text-xs text-white/35">
              {t("company:jobs.kanban.aiSubtitle")}
            </p>
            <JobRecommendations key={job.id} jobId={job.id} />
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Job list item ────────────────────────────────────────────────────────────

interface JobListItemProps {
  job: JobRead;
  isSelected: boolean;
  onClick: () => void;
}

function JobListItem({ job, isSelected, onClick }: JobListItemProps) {
  const { t } = useTranslation("company");

  const STATUS_COLOR: Record<string, string> = {
    PENDING_APPROVAL: "bg-warning/10 text-warning",
    PUBLISHED: "bg-success/10 text-success",
    CLOSED: "bg-white/8 text-white/40",
  };
  const STATUS_LABEL: Record<string, string> = {
    PENDING_APPROVAL: t("company:jobs.statusLabels.PENDING_APPROVAL"),
    PUBLISHED: t("company:jobs.statusLabels.PUBLISHED"),
    CLOSED: t("company:jobs.statusLabels.CLOSED"),
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-xl border p-4 text-start transition ${
        isSelected
          ? "border-copper/40 bg-card-raised"
          : "border-white/8 bg-card hover:border-white/15 hover:bg-card-raised"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="truncate text-sm font-medium text-white/85">{job.title}</span>
        <StatusBadge
          label={STATUS_LABEL[job.status]}
          colorCls={STATUS_COLOR[job.status]}
        />
      </div>
      <p className="mt-0.5 text-xs text-white/40">{job.location}</p>
      <p className="mt-1 text-xs text-white/25">
        {t("company:jobs.postedLabel")} {formatDate(job.created_at)}
      </p>
    </button>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Mode = "idle" | "create" | { type: "edit"; job: JobRead };

export default function CompanyJobsPage() {
  const { t } = useTranslation(["common", "company"]);
  const [mode, setMode] = useState<Mode>("idle");
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const fetcher = useCallback((cursor: string | null) => getCompanyJobs(cursor), []);
  const {
    items: jobs,
    isLoading: loading,
    isFetchingMore,
    hasMore,
    error: loadError,
    sentinelRef,
    prependItem,
    updateItem,
    removeItem,
  } = useInfiniteList<JobRead>(fetcher);

  const error = loadError ? t("company:jobs.errors.loadFailed") : mutationError;
  const selectedJob = jobs.find((j) => j.id === selectedJobId) ?? null;
  const isShowingForm =
    mode === "create" || (typeof mode === "object" && mode.type === "edit");

  async function handleCreate(data: JobCreate) {
    const job = await createJob(data);
    prependItem(job);
    setMode("idle");
    setSelectedJobId(job.id);
  }

  async function handleEdit(jobId: number, data: JobCreate) {
    const update: JobUpdate = { ...data };
    const job = await updateJob(jobId, update);
    updateItem((j) => j.id === jobId, job);
    setMode("idle");
  }

  async function handleDelete(jobId: number) {
    if (!confirm(t("company:jobs.deleteConfirm"))) return;
    setDeleting(jobId);
    setMutationError(null);
    try {
      await deleteJob(jobId);
      removeItem((j) => j.id === jobId);
      if (selectedJobId === jobId) setSelectedJobId(null);
    } catch {
      setMutationError(t("company:jobs.errors.deleteFailed"));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("company:jobs.title")}
        subtitle={t("company:jobs.subtitle")}
        action={
          !isShowingForm ? (
            <Button onClick={() => { setMode("create"); setSelectedJobId(null); }}>
              {t("company:jobs.postJob")}
            </Button>
          ) : undefined
        }
      />

      {error && (
        <div className={`mb-4 ${errorAlertBaseCls} p-4`}>{error}</div>
      )}

      {/* Create / edit form */}
      {isShowingForm && (
        <div className="mb-6 rounded-xl border border-copper/20 bg-card p-6">
          <Eyebrow className="mb-4">
            {mode === "create"
              ? t("company:jobs.createTitle")
              : t("company:jobs.editTitle")}
          </Eyebrow>
          <JobForm
            initial={
              typeof mode === "object" && mode.type === "edit"
                ? {
                    title: mode.job.title,
                    short_description: mode.job.short_description,
                    description: mode.job.description,
                    requirements:
                      mode.job.requirements.length > 0
                        ? mode.job.requirements.map((r) => ({ text: r.text }))
                        : emptyRequirements(),
                    tags: [...mode.job.tags],
                    location: mode.job.location,
                    salary_min: mode.job.salary_min ?? 0,
                    salary_max: mode.job.salary_max ?? 0,
                  }
                : EMPTY_FORM
            }
            onSubmit={
              typeof mode === "object" && mode.type === "edit"
                ? (data) => handleEdit(mode.job.id, data)
                : handleCreate
            }
            onCancel={() => setMode("idle")}
            submitLabel={
              mode === "create"
                ? t("company:jobs.submitForReview")
                : t("company:jobs.saveChanges")
            }
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16 text-white/25">
          {t("company:jobs.loading")}
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
          {t("company:jobs.empty")}
        </div>
      ) : (
        /* Two-panel layout */
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          {/* Left: job list */}
          <div className="space-y-2">
            {jobs.map((job) => (
              <JobListItem
                key={job.id}
                job={job}
                isSelected={selectedJobId === job.id}
                onClick={() => {
                  setSelectedJobId(job.id);
                  setMode("idle");
                }}
              />
            ))}
            {(hasMore || isFetchingMore) && (
              <div
                ref={sentinelRef}
                className="py-2 text-center text-xs text-white/25"
              >
                {isFetchingMore ? t("common:loading") : ""}
              </div>
            )}
          </div>

          {/* Right: detail + kanban */}
          <div className="rounded-xl border border-white/8 bg-card p-5">
            {selectedJob ? (
              <JobDetailPanel
                job={selectedJob}
                onEdit={() => setMode({ type: "edit", job: selectedJob })}
                onDelete={() => handleDelete(selectedJob.id)}
                isDeleting={deleting === selectedJob.id}
                editingDisabled={isShowingForm}
              />
            ) : (
              <div className="flex h-48 items-center justify-center text-sm text-white/25">
                {t("company:jobs.kanban.selectJob")}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

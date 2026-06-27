import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import Button from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import JobKanban from "@/pages/company/components/JobKanban";
import JobRecommendations from "@/pages/company/components/JobRecommendations";
import { deleteJob, getCompanyJob } from "@/services/companyJobs";
import { JobStatus } from "@/types/enums";
import type { JobRead } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

const STATUS_LABEL_KEYS: Record<string, string> = {
  PENDING_APPROVAL: "company:jobs.statusLabels.PENDING_APPROVAL",
  PUBLISHED: "company:jobs.statusLabels.PUBLISHED",
  CLOSED: "company:jobs.statusLabels.CLOSED",
};

const STATUS_COLOR: Record<string, string> = {
  PENDING_APPROVAL: "bg-warning/10 text-warning",
  PUBLISHED: "bg-success/10 text-success",
  CLOSED: "bg-white/8 text-white/40",
};

type DetailTab = "kanban" | "ai";

export default function CompanyJobKanbanPage() {
  const { t } = useTranslation("company");
  const navigate = useNavigate();
  const { jobId: jobIdParam } = useParams<{ jobId: string }>();
  const jobId = Number(jobIdParam);

  const [job, setJob] = useState<JobRead | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<DetailTab>("kanban");
  const [isDeleting, setIsDeleting] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  useEffect(() => {
    if (isNaN(jobId)) { navigate("/company/jobs"); return; }
    let cancelled = false;
    getCompanyJob(jobId)
      .then((j) => { if (!cancelled) setJob(j); })
      .catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; };
  }, [jobId, navigate]);

  async function handleDelete() {
    if (!job || !confirm(t("company:jobs.deleteConfirm"))) return;
    setIsDeleting(true);
    setMutationError(null);
    try {
      await deleteJob(job.id);
      navigate("/company/jobs");
    } catch {
      setMutationError(t("company:jobs.errors.deleteFailed"));
      setIsDeleting(false);
    }
  }

  if (isNaN(jobId)) return null;

  if (loadError) {
    return (
      <div className="py-20 text-center text-sm text-danger">
        {t("company:jobs.errors.loadFailed")}
      </div>
    );
  }

  const canEdit =
    !!job &&
    (job.status === JobStatus.PENDING_APPROVAL || job.status === JobStatus.PUBLISHED);
  const canDelete = !!job && job.status === JobStatus.PENDING_APPROVAL;

  return (
    <div>
      <PageHeader eyebrow={t("company:jobs.title")} />

      <button
        type="button"
        onClick={() => navigate("/company/jobs")}
        className="mb-5 flex items-center gap-1.5 text-sm text-white/40 transition hover:text-white/70"
      >
        <span aria-hidden>→</span>
        {t("company:jobs.backToList")}
      </button>

      {mutationError && (
        <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
          {mutationError}
        </div>
      )}

      {job ? (
        <>
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold text-white/90">{job.title}</h2>
                <StatusBadge
                  label={t(STATUS_LABEL_KEYS[job.status] ?? "")}
                  colorCls={STATUS_COLOR[job.status] ?? ""}
                />
              </div>
              <p className="text-sm text-white/45">{job.location}</p>
              <p className="mt-0.5 text-xs text-white/25">
                {t("company:jobs.postedLabel")} {formatDate(job.created_at)}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              {canEdit && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate(`/company/jobs/${jobId}/edit`)}
                >
                  {t("company:jobs.edit")}
                </Button>
              )}
              {canDelete && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleDelete}
                  disabled={isDeleting}
                >
                  {isDeleting ? "…" : t("company:jobs.delete")}
                </Button>
              )}
            </div>
          </div>

          <div className="mb-4 flex gap-1 border-b border-white/8">
            {(["kanban", "ai"] as DetailTab[]).map((tab_) => (
              <button
                key={tab_}
                type="button"
                onClick={() => setTab(tab_)}
                className={`px-3 py-2 text-sm transition ${
                  tab === tab_
                    ? "border-b-2 border-copper font-medium text-copper"
                    : "text-white/40 hover:text-white/70"
                }`}
              >
                {tab_ === "kanban"
                  ? t("company:jobs.kanban.title")
                  : t("company:jobs.kanban.aiTitle")}
              </button>
            ))}
          </div>

          {tab === "kanban" ? (
            <JobKanban jobId={job.id} />
          ) : (
            <div>
              <p className="mb-3 text-xs text-white/35">
                {t("company:jobs.kanban.aiSubtitle")}
              </p>
              <JobRecommendations jobId={job.id} />
            </div>
          )}
        </>
      ) : (
        <div className="space-y-3 py-4">
          <div className="h-6 w-48 animate-pulse rounded-lg bg-white/8" />
          <div className="h-4 w-32 animate-pulse rounded bg-white/5" />
        </div>
      )}
    </div>
  );
}

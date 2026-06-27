import { useCallback, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import JobForm from "@/pages/company/components/JobForm";
import { emptyRequirements } from "@/pages/company/components/JobFormUtils";
import { deleteJob, getCompanyJobs, updateJob } from "@/services/companyJobs";
import { getMyCompanyStats } from "@/services/companyProfile";
import { errorAlertCls } from "@/styles/forms";
import type { CompanyStats } from "@/types/companies";
import { JobStatus } from "@/types/enums";
import type { JobCreate, JobRead, JobUpdate } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

// ─── Status maps ──────────────────────────────────────────────────────────────

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

// ─── Stats row ────────────────────────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-white/90">{value}</p>
    </div>
  );
}

function StatsRow({ stats }: { stats: CompanyStats | null }) {
  const { t } = useTranslation("company");
  const em = "—";
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard label={t("company:dashboard.activeJobs")} value={stats?.active_jobs ?? em} />
      <StatCard label={t("company:dashboard.pendingJobs")} value={stats?.pending_jobs ?? em} />
      <StatCard label={t("company:dashboard.closedJobs")} value={stats?.closed_jobs ?? em} />
      <StatCard
        label={t("company:dashboard.totalApplications")}
        value={stats?.total_applications ?? em}
      />
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type Mode = "idle" | { type: "edit"; job: JobRead };

export default function CompanyJobsPage() {
  const { t } = useTranslation(["common", "company"]);
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("idle");
  const [deleting, setDeleting] = useState<number | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [stats, setStats] = useState<CompanyStats | null>(null);

  const fetcher = useCallback((cursor: string | null) => getCompanyJobs(cursor), []);
  const {
    items: jobs,
    isLoading: loading,
    isFetchingMore,
    hasMore,
    error: loadError,
    sentinelRef,
    updateItem,
    removeItem,
  } = useInfiniteList<JobRead>(fetcher);

  useEffect(() => {
    let cancelled = false;
    getMyCompanyStats()
      .then((s) => { if (!cancelled) setStats(s); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const error = loadError ? t("company:jobs.errors.loadFailed") : mutationError;
  const isEditingInline = typeof mode === "object" && mode.type === "edit";

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
          !isEditingInline ? (
            <Button onClick={() => navigate("/company/jobs/new")}>{t("company:jobs.postJob")}</Button>
          ) : undefined
        }
      />

      <StatsRow stats={stats} />

      {error && <div className={`mb-4 ${errorAlertCls}`}>{error}</div>}

      {isEditingInline && typeof mode === "object" && (
        <div className="mb-6 rounded-xl border border-copper/20 bg-card p-6">
          <Eyebrow className="mb-4">{t("company:jobs.editTitle")}</Eyebrow>
          <JobForm
            initial={{
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
            }}
            onSubmit={(data) => handleEdit(mode.job.id, data)}
            onCancel={() => setMode("idle")}
            submitLabel={t("company:jobs.saveChanges")}
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16 text-white/25">{t("company:jobs.loading")}</div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
          {t("company:jobs.empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-white/8">
          <table className="min-w-full divide-y divide-white/6 text-sm">
            <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
              <tr>
                <th className="px-4 py-3 text-start">{t("company:jobs.table.title")}</th>
                <th className="px-4 py-3 text-start">{t("company:jobs.table.location")}</th>
                <th className="px-4 py-3 text-start">{t("company:jobs.table.status")}</th>
                <th className="px-4 py-3 text-start">{t("company:jobs.table.posted")}</th>
                <th className="px-4 py-3 text-end" aria-hidden />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/6 bg-card">
              {jobs.map((job) => {
                const canEdit =
                  job.status === JobStatus.PENDING_APPROVAL ||
                  job.status === JobStatus.PUBLISHED;
                const canDelete = job.status === JobStatus.PENDING_APPROVAL;
                return (
                  <tr
                    key={job.id}
                    onClick={() => navigate(`/company/jobs/${job.id}`)}
                    className="cursor-pointer transition hover:bg-white/3"
                  >
                    <td className="px-4 py-3 font-medium text-white/90">{job.title}</td>
                    <td className="px-4 py-3 text-white/45">{job.location}</td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        label={t(STATUS_LABEL_KEYS[job.status] ?? "")}
                        colorCls={STATUS_COLOR[job.status] ?? ""}
                      />
                    </td>
                    <td className="px-4 py-3 text-white/40">{formatDate(job.created_at)}</td>
                    <td
                      className="px-4 py-3 text-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setMode({ type: "edit", job })}
                          >
                            {t("company:jobs.edit")}
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => handleDelete(job.id)}
                          >
                            {deleting === job.id ? "…" : t("company:jobs.delete")}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {(hasMore || isFetchingMore) && (
            <div ref={sentinelRef} className="py-2 text-center text-xs text-white/25">
              {isFetchingMore ? t("common:loading") : ""}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

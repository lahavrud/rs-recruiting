import { useCallback, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import { deleteJob, getCompanyJobs } from "@/services/companyJobs";
import { getMyCompanyStats } from "@/services/companyProfile";
import { errorAlertCls } from "@/styles/forms";
import type { CompanyStats } from "@/types/companies";
import { JobStatus } from "@/types/enums";
import type { JobRead } from "@/types/jobs";
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
      <Eyebrow>{label}</Eyebrow>
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

export default function CompanyJobsPage() {
  const { t } = useTranslation(["common", "company"]);
  const navigate = useNavigate();
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
          <Button onClick={() => navigate("/company/jobs/new")}>{t("company:jobs.postJob")}</Button>
        }
      />

      <StatsRow stats={stats} />

      {error && <div className={`mb-4 ${errorAlertCls}`}>{error}</div>}

      {loading ? (
        <div className="flex justify-center py-16 text-white/25">{t("company:jobs.loading")}</div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
          {t("company:jobs.empty")}
        </div>
      ) : (
        <>
        {/* Mobile card list */}
        <div className="sm:hidden divide-y divide-white/6 overflow-hidden rounded-xl border border-white/8">
          {jobs.map((job) => {
            const canEdit =
              job.status === JobStatus.PENDING_APPROVAL ||
              job.status === JobStatus.PUBLISHED;
            const canDelete = job.status === JobStatus.PENDING_APPROVAL;
            return (
              <div
                key={job.id}
                onClick={() => navigate(`/company/jobs/${job.id}`)}
                className="flex cursor-pointer flex-col gap-2.5 bg-card p-4 transition hover:bg-card-raised"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium leading-snug text-white/90">{job.title}</p>
                  <StatusBadge
                    label={t(STATUS_LABEL_KEYS[job.status] ?? "")}
                    colorCls={STATUS_COLOR[job.status] ?? ""}
                  />
                </div>
                <p className="text-sm text-white/45">{job.location}</p>
                <div
                  className="flex items-center justify-between pt-0.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  <p className="text-xs text-white/30">{formatDate(job.created_at)}</p>
                  <div className="flex gap-1">
                    {canEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/company/jobs/${job.id}/edit`)}
                      >
                        {t("company:jobs.edit")}
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={deleting === job.id}
                        onClick={() => handleDelete(job.id)}
                      >
                        {deleting === job.id ? "…" : t("company:jobs.delete")}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Desktop table */}
        <div className="hidden sm:block overflow-hidden rounded-xl border border-white/8">
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
                            onClick={() => navigate(`/company/jobs/${job.id}/edit`)}
                          >
                            {t("company:jobs.edit")}
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="danger"
                            size="sm"
                            disabled={deleting === job.id}
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
        </div>

        {/* Shared infinite-scroll sentinel — must be outside display:none containers */}
        {(hasMore || isFetchingMore) && (
          <div ref={sentinelRef} className="py-2 text-center text-xs text-white/25">
            {isFetchingMore ? t("common:loading") : ""}
          </div>
        )}
        </>
      )}
    </div>
  );
}

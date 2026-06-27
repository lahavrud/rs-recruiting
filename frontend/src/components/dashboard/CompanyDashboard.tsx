import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import { getMyCompanyStats } from "@/services/companyProfile";
import type { CompanyStats } from "@/types/companies";
import { ApplicationStatus } from "@/types/enums";

const STATUS_LABEL: Record<string, string> = {
  [ApplicationStatus.NEW]: "חדש",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "מאושר",
  [ApplicationStatus.HIRED]: "גויס",
  [ApplicationStatus.REJECTED]: "נדחה",
  [ApplicationStatus.WITHDRAWN]: "נסוג",
  [ApplicationStatus.JOB_CLOSED]: "משרה סגורה",
};

const STATUS_COLOR: Record<string, string> = {
  [ApplicationStatus.NEW]: "bg-info/15 text-info",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "bg-copper/15 text-copper",
  [ApplicationStatus.HIRED]: "bg-hired/15 text-hired",
  [ApplicationStatus.REJECTED]: "bg-danger/15 text-danger",
  [ApplicationStatus.WITHDRAWN]: "bg-white/8 text-white/40",
  [ApplicationStatus.JOB_CLOSED]: "bg-white/8 text-white/30",
};

const STATUS_BAR_COLOR: Record<string, string> = {
  [ApplicationStatus.NEW]: "bg-info",
  [ApplicationStatus.APPROVED_BY_ADMIN]: "bg-copper",
  [ApplicationStatus.HIRED]: "bg-hired",
  [ApplicationStatus.REJECTED]: "bg-danger",
  [ApplicationStatus.WITHDRAWN]: "bg-white/20",
  [ApplicationStatus.JOB_CLOSED]: "bg-white/15",
};

interface StatCardProps {
  label: string;
  value: number;
  hint?: string;
  to?: string;
  accent?: "copper" | "success" | "warning" | "info";
}

function StatCard({ label, value, hint, to, accent = "copper" }: StatCardProps) {
  const accentCls: Record<string, string> = {
    copper: "text-copper",
    success: "text-success",
    warning: "text-warning",
    info: "text-info",
  };
  const inner = (
    <div className="rounded-xl border border-white/8 bg-card p-5">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-white/35">
        {label}
      </p>
      <p className={`mt-2 text-3xl font-semibold tabular-nums ${accentCls[accent]}`}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-white/35">{hint}</p>}
    </div>
  );
  if (to) {
    return (
      <Link
        to={to}
        className="block transition duration-200 hover:opacity-90"
      >
        {inner}
      </Link>
    );
  }
  return inner;
}

export default function CompanyDashboard() {
  const { t } = useTranslation("company");
  const [stats, setStats] = useState<CompanyStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyCompanyStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-xl border border-white/8 bg-card"
          />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const totalByStatus = Object.entries(stats.applications_by_status).filter(
    ([, count]) => count > 0,
  );
  const maxCount = Math.max(...totalByStatus.map(([, c]) => c), 1);

  return (
    <div className="space-y-8">
      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("company:dashboard.activeJobs")}
          value={stats.active_jobs}
          hint={t("company:dashboard.activeJobsHint")}
          to="/company/jobs"
          accent="success"
        />
        <StatCard
          label={t("company:dashboard.pendingJobs")}
          value={stats.pending_jobs}
          hint={t("company:dashboard.pendingJobsHint")}
          to="/company/jobs"
          accent="warning"
        />
        <StatCard
          label={t("company:dashboard.totalApplications")}
          value={stats.total_applications}
          hint={t("company:dashboard.totalApplicationsHint")}
        />
        <StatCard
          label={t("company:dashboard.closedJobs")}
          value={stats.closed_jobs}
          hint={t("company:dashboard.closedJobsHint")}
          accent="info"
        />
      </div>

      {/* Applications breakdown */}
      {totalByStatus.length > 0 && (
        <div className="rounded-xl border border-white/8 bg-card p-6">
          <Eyebrow className="mb-5">{t("company:dashboard.applicationsBreakdown")}</Eyebrow>
          <div className="space-y-3">
            {totalByStatus.map(([status, count]) => (
              <div key={status} className="flex items-center gap-3">
                <span
                  className={`w-28 shrink-0 rounded-full px-2.5 py-0.5 text-center text-[10px] font-semibold uppercase tracking-wider ${STATUS_COLOR[status] ?? "bg-white/8 text-white/40"}`}
                >
                  {STATUS_LABEL[status] ?? status}
                </span>
                <div className="flex flex-1 items-center gap-2">
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/6">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${STATUS_BAR_COLOR[status] ?? "bg-white/20"}`}
                      style={{ width: `${(count / maxCount) * 100}%` }}
                    />
                  </div>
                  <span className="w-6 text-end text-xs font-medium tabular-nums text-white/60">
                    {count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick links */}
      <div>
        <Eyebrow className="mb-4">{t("company:dashboard.quickActions")}</Eyebrow>
        <div className="grid gap-3 sm:grid-cols-2">
          <Link
            to="/company/jobs"
            className="group rounded-xl border border-white/8 bg-card p-5 transition duration-200 hover:border-copper/30 hover:bg-card-raised"
          >
            <p className="font-medium text-white/85 transition group-hover:text-white/95">
              {t("company:dashboard.manageJobs")}
            </p>
            <p className="mt-1 text-sm text-white/45">
              {t("company:dashboard.manageJobsDesc")}
            </p>
          </Link>
          <Link
            to="/company/profile"
            className="group rounded-xl border border-white/8 bg-card p-5 transition duration-200 hover:border-copper/30 hover:bg-card-raised"
          >
            <p className="font-medium text-white/85 transition group-hover:text-white/95">
              {t("company:dashboard.companyProfile")}
            </p>
            <p className="mt-1 text-sm text-white/45">
              {t("company:dashboard.companyProfileDesc")}
            </p>
          </Link>
        </div>
      </div>
    </div>
  );
}

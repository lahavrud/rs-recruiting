import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { APPLICATION_STATUS_META } from "@/constants/statusColors";
import { getAdminOverview, type AdminStatsCounts } from "@/services/adminOverview";
import { ApplicationStatus } from "@/types/enums";

export default function AdminStats() {
  const { t } = useTranslation(["common", "dashboard"]);
  const [stats, setStats] = useState<AdminStatsCounts | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then((data) => setStats(data.stats))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  const kpis = [
    {
      label: t("dashboard:stats.activeCompanies"),
      n: stats?.active_companies ?? null,
    },
    {
      label: t("dashboard:stats.publishedJobs"),
      n: stats?.published_jobs ?? null,
    },
    {
      label: t("dashboard:stats.candidates"),
      n: stats?.total_candidates ?? null,
    },
    {
      label: t("dashboard:stats.hired"),
      n: stats?.application_status_counts[ApplicationStatus.HIRED] ?? null,
    },
  ];

  const statusCounts = stats?.application_status_counts ?? {};
  const topJobs = stats?.top_jobs ?? [];

  return (
    <div className="space-y-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("dashboard:stats.title")}
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {kpis.map((k) => (
          <KpiCard key={k.label} label={k.label} n={k.n} />
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_280px]">
        <ApplicationStatusBar counts={statusCounts} />
        <TopJobsList jobs={topJobs} isLoading={stats == null} />
      </div>
    </div>
  );
}

function KpiCard({ label, n }: { label: string; n: number | null }) {
  const isLoading = n == null;
  const isEmpty = !isLoading && n === 0;
  const display = isLoading ? "—" : n;
  return (
    <div className="group rounded-xl border border-white/8 bg-card p-4 transition hover:border-copper/30 hover:bg-card-raised">
      <p
        className={`text-3xl font-semibold leading-none transition ${
          isLoading
            ? "text-white/25"
            : isEmpty
              ? "text-white/45"
              : "text-white/95 group-hover:text-copper/95"
        }`}
      >
        {display}
      </p>
      <p className="mt-2 text-xs font-medium text-white/55">{label}</p>
    </div>
  );
}

function ApplicationStatusBar({ counts }: { counts: Record<string, number> }) {
  const { t } = useTranslation(["common", "dashboard"]);
  const segments = [
    { status: ApplicationStatus.NEW, n: counts[ApplicationStatus.NEW] ?? 0 },
    {
      status: ApplicationStatus.APPROVED_BY_ADMIN,
      n: counts[ApplicationStatus.APPROVED_BY_ADMIN] ?? 0,
    },
    { status: ApplicationStatus.HIRED, n: counts[ApplicationStatus.HIRED] ?? 0 },
    {
      status: ApplicationStatus.REJECTED,
      n: counts[ApplicationStatus.REJECTED] ?? 0,
    },
  ];
  const total = segments.reduce((a, s) => a + s.n, 0);
  return (
    <div className="rounded-xl border border-white/8 bg-card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("dashboard:stats.statusBreakdown")}
      </p>
      {total === 0 ? (
        <p className="mt-3 text-sm text-white/40">
          {t("dashboard:stats.noApplications")}
        </p>
      ) : (
        <>
          <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-white/5">
            {segments.map((seg) =>
              seg.n === 0 ? null : (
                <div
                  key={seg.status}
                  className={APPLICATION_STATUS_META[seg.status].barClass}
                  style={{ width: `${(seg.n / total) * 100}%` }}
                  title={`${t(`admin:applications.statusLabels.${seg.status}`)} — ${seg.n}`}
                />
              ),
            )}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
            {segments.map((seg) => (
              <div key={seg.status} className="inline-flex items-center gap-1.5">
                <span
                  className={`size-2.5 rounded-full ${APPLICATION_STATUS_META[seg.status].dotClass}`}
                  aria-hidden="true"
                />
                <span className="text-white/55">
                  {t(`admin:applications.statusLabels.${seg.status}`)}
                </span>
                <span className="font-medium text-white/85">{seg.n}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TopJobsList({
  jobs,
  isLoading,
}: {
  jobs: { id: number; title: string; application_count: number }[];
  isLoading: boolean;
}) {
  const { t } = useTranslation(["common", "dashboard"]);
  const maxCount = jobs[0]?.application_count ?? 0;
  return (
    <div className="rounded-xl border border-white/8 bg-card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("dashboard:stats.topJobs")}
      </p>
      {isLoading ? (
        <p className="mt-3 text-sm text-white/40">{t("common:loading")}</p>
      ) : jobs.length === 0 ? (
        <p className="mt-3 text-sm text-white/40">{t("dashboard:stats.noTopJobs")}</p>
      ) : (
        <ol className="mt-3 space-y-2">
          {jobs.map((j) => (
            <li key={j.id}>
              <Link
                to={`/admin/applications?job=${j.id}`}
                className="group flex items-center gap-3"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-white/80 transition group-hover:text-copper">
                    {j.title}
                  </span>
                  <span className="mt-1 block h-1 rounded-full bg-white/5">
                    <span
                      className="block h-1 rounded-full bg-copper/70"
                      style={{
                        width:
                          maxCount === 0
                            ? "0%"
                            : `${(j.application_count / maxCount) * 100}%`,
                      }}
                    />
                  </span>
                </span>
                <span className="font-mono text-xs font-medium text-white/70 tabular-nums">
                  {j.application_count}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

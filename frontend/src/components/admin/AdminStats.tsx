import { useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { APPLICATION_STATUS_META } from "@/constants/statusColors";
import { getApplications } from "@/services/adminApplications";
import { getCandidates } from "@/services/adminCandidates";
import { getActiveCompanies } from "@/services/adminCompanies";
import { getJobs } from "@/services/adminJobs";
import {
  ApplicationStatus,
  JobStatus,
  type ApplicationWithDetails,
} from "@/types/api";

/**
 * Dashboard stats block. Three sub-sections, all fed by parallel first-page
 * fetches (capped at 100 items each — backend's MAX_LIMIT):
 *
 *   - 4 KPI cards (active companies, published jobs, candidates, hired)
 *   - Application status breakdown bar
 *   - Top 5 jobs by application count
 */

const LIMIT = 100;
type Stat = { n: number; capped: boolean } | null;

export default function AdminStats() {
  const { t } = useTranslation(['common', 'dashboard']);
  const [activeCompanies, setActiveCompanies] = useState<Stat>(null);
  const [publishedJobs, setPublishedJobs] = useState<Stat>(null);
  const [candidates, setCandidates] = useState<Stat>(null);
  const [hired, setHired] = useState<Stat>(null);
  const [appCache, setAppCache] = useState<ApplicationWithDetails[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    function toStat<T>(page: { items: T[]; next_cursor: string | null }): Stat {
      return { n: page.items.length, capped: page.next_cursor != null };
    }
    getActiveCompanies({ limit: LIMIT }, ctrl.signal)
      .then((p) => setActiveCompanies(toStat(p)))
      .catch(() => {});
    getJobs({ status: JobStatus.PUBLISHED, limit: LIMIT }, ctrl.signal)
      .then((p) => setPublishedJobs(toStat(p)))
      .catch(() => {});
    getCandidates({ limit: LIMIT }, ctrl.signal)
      .then((p) => setCandidates(toStat(p)))
      .catch(() => {});
    getApplications(
      { status: ApplicationStatus.HIRED, limit: LIMIT },
      ctrl.signal,
    )
      .then((p) => setHired(toStat(p)))
      .catch(() => {});
    getApplications({ limit: LIMIT }, ctrl.signal)
      .then((p) => setAppCache(p.items))
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  const statusBreakdown = useMemo(() => {
    const counts: { [k: string]: number } = {
      [ApplicationStatus.NEW]: 0,
      [ApplicationStatus.APPROVED_BY_ADMIN]: 0,
      [ApplicationStatus.REJECTED]: 0,
      [ApplicationStatus.HIRED]: 0,
    };
    for (const a of appCache) counts[a.status] = (counts[a.status] ?? 0) + 1;
    return counts;
  }, [appCache]);

  const topJobs = useMemo(() => {
    const grouped = new Map<number, { title: string; count: number }>();
    for (const a of appCache) {
      const cur = grouped.get(a.job_id);
      grouped.set(a.job_id, {
        title: cur?.title ?? a.job.title,
        count: (cur?.count ?? 0) + 1,
      });
    }
    return Array.from(grouped.entries())
      .map(([id, v]) => ({ id, title: v.title, count: v.count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [appCache]);

  const kpis = [
    { label: t("dashboard:stats.activeCompanies"), stat: activeCompanies },
    { label: t("dashboard:stats.publishedJobs"), stat: publishedJobs },
    { label: t("dashboard:stats.candidates"), stat: candidates },
    { label: t("dashboard:stats.hired"), stat: hired },
  ];

  return (
    <div className="space-y-5">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("dashboard:stats.title")}
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {kpis.map((k) => (
          <KpiCard key={k.label} label={k.label} stat={k.stat} />
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_280px]">
        <ApplicationStatusBar counts={statusBreakdown} />
        <TopJobsList jobs={topJobs} loading={appCache.length === 0} />
      </div>
    </div>
  );
}

function KpiCard({ label, stat }: { label: string; stat: Stat }) {
  const loading = stat == null;
  const empty = !loading && stat!.n === 0;
  const display = loading
    ? "—"
    : stat!.capped
      ? `${stat!.n}+`
      : stat!.n;
  return (
    <div className="group rounded-xl border border-white/8 bg-card p-4 transition hover:border-copper/30 hover:bg-card-raised">
      <p
        className={`text-3xl font-semibold leading-none transition ${
          loading
            ? "text-white/25"
            : empty
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

function ApplicationStatusBar({
  counts,
}: {
  counts: { [k: string]: number };
}) {
  const { t } = useTranslation(['common', 'dashboard']);
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
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
              <div
                key={seg.status}
                className="inline-flex items-center gap-1.5"
              >
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
  loading,
}: {
  jobs: { id: number; title: string; count: number }[];
  loading: boolean;
}) {
  const { t } = useTranslation(['common', 'dashboard']);
  const maxCount = jobs[0]?.count ?? 0;
  return (
    <div className="rounded-xl border border-white/8 bg-card p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("dashboard:stats.topJobs")}
      </p>
      {loading ? (
        <p className="mt-3 text-sm text-white/40">{t("common:loading")}</p>
      ) : jobs.length === 0 ? (
        <p className="mt-3 text-sm text-white/40">
          {t("dashboard:stats.noTopJobs")}
        </p>
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
                        width: maxCount === 0 ? "0%" : `${(j.count / maxCount) * 100}%`,
                      }}
                    />
                  </span>
                </span>
                <span className="font-mono text-xs font-medium text-white/70 tabular-nums">
                  {j.count}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Eyebrow from "@/components/ui/Eyebrow";
import { APPLICATION_STATUS_META } from "@/constants/statusColors";
import { getAdminOverview, type AdminOverviewRead, type TrendPoint } from "@/services/adminOverview";
import { ApplicationStatus } from "@/types/enums";

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const CHART_COPPER = cssVar("--color-copper");
const CHART_GRID = "rgba(255,255,255,0.06)";
const CHART_TICK = "rgba(255,255,255,0.28)";
const CHART_BG = cssVar("--color-card-raised");
const CHART_BORDER = "rgba(255,255,255,0.08)";
const CHART_SUCCESS = cssVar("--color-success");
const CHART_DANGER = cssVar("--color-danger");
const CHART_HIRED = cssVar("--color-hired");

const PIPELINE_FILL: Record<string, string> = {
  [ApplicationStatus.NEW]: CHART_COPPER,
  [ApplicationStatus.APPROVED_BY_ADMIN]: CHART_SUCCESS,
  [ApplicationStatus.HIRED]: CHART_HIRED,
  [ApplicationStatus.REJECTED]: CHART_DANGER,
};

export default function AdminStats() {
  const { t } = useTranslation(["common", "dashboard", "admin"]);
  const [overview, setOverview] = useState<AdminOverviewRead | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAdminOverview(ctrl.signal)
      .then(setOverview)
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  const stats = overview?.stats ?? null;
  const pulse = overview?.pulse ?? null;

  const totalApps =
    stats != null
      ? Object.values(stats.application_status_counts).reduce((a, b) => a + b, 0)
      : null;

  const kpis = [
    {
      label: t("dashboard:stats.activeCompanies"),
      n: stats?.active_companies ?? null,
      weekDelta: null,
      to: "/admin/companies",
    },
    {
      label: t("dashboard:stats.publishedJobs"),
      n: stats?.published_jobs ?? null,
      weekDelta: null,
      to: "/admin/jobs",
    },
    {
      label: t("dashboard:stats.candidates"),
      n: stats?.total_candidates ?? null,
      weekDelta: pulse?.new_candidates_7d ?? null,
      to: "/admin/candidates",
    },
    {
      label: t("dashboard:stats.totalApplications"),
      n: totalApps,
      weekDelta: pulse?.new_applications_7d ?? null,
      to: "/admin/applications",
    },
  ];

  return (
    <div className="space-y-5">
      <Eyebrow>{t("dashboard:stats.title")}</Eyebrow>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis.map((k) => (
          <KpiCard key={k.label} label={k.label} n={k.n} weekDelta={k.weekDelta} to={k.to} />
        ))}
      </div>

      {/* Charts row */}
      <div className="grid gap-3 lg:grid-cols-[1fr_320px]">
        <TrendChart points={pulse?.trend_30d ?? null} />
        <PipelineFunnel counts={stats?.application_status_counts ?? null} />
      </div>

      {/* Top jobs */}
      <TopJobsList jobs={stats?.top_jobs ?? []} isLoading={stats == null} />
    </div>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  n,
  weekDelta,
  to,
}: {
  label: string;
  n: number | null;
  weekDelta: number | null;
  to: string;
}) {
  const { t } = useTranslation("dashboard");
  const isLoading = n == null;
  const isEmpty = !isLoading && n === 0;
  return (
    <Link
      to={to}
      className="group rounded-xl border border-white/8 bg-card p-4 transition hover:border-copper/30 hover:bg-card-raised"
    >
      <p
        className={`text-3xl font-semibold leading-none tabular-nums transition ${
          isLoading
            ? "text-white/25"
            : isEmpty
              ? "text-white/45"
              : "text-white/95 group-hover:text-copper/95"
        }`}
      >
        {isLoading ? "—" : n}
      </p>
      <p className="mt-2 text-xs font-medium text-white/55">{label}</p>
      {weekDelta != null && weekDelta > 0 && (
        <p className="mt-1.5 text-[10px] font-semibold text-success/80">
          {t("dashboard:pulse.newThisWeek", { count: weekDelta })}
        </p>
      )}
    </Link>
  );
}

// ── 30-day trend area chart ───────────────────────────────────────────────────

function TrendChart({ points }: { points: TrendPoint[] | null }) {
  const { t } = useTranslation("dashboard");

  const data =
    points?.map((p) => {
      const d = new Date(p.date);
      return { label: `${d.getDate()}/${d.getMonth() + 1}`, n: p.n };
    }) ?? [];

  const hasActivity = data.some((d) => d.n > 0);

  return (
    <div className="rounded-xl border border-white/8 bg-card p-4">
      <Eyebrow>{t("dashboard:trend.title")}</Eyebrow>

      {points == null ? (
        <div className="mt-3 h-36 animate-pulse rounded-lg bg-white/5" />
      ) : !hasActivity ? (
        <p className="mt-3 text-sm text-white/35">{t("dashboard:trend.empty")}</p>
      ) : (
        /* dir="ltr" isolates the chart from the page's RTL direction */
        <div dir="ltr" className="mt-4 h-36">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
              <defs>
                <linearGradient id="copperGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={CHART_COPPER} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={CHART_COPPER} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={CHART_GRID}
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fill: CHART_TICK, fontSize: 9 }}
                tickLine={false}
                axisLine={false}
                interval={4}
              />
              <YAxis
                tick={{ fill: CHART_TICK, fontSize: 9 }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
                width={30}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: CHART_BG,
                  border: `1px solid ${CHART_BORDER}`,
                  borderRadius: "8px",
                  fontSize: "11px",
                  color: "rgba(255,255,255,0.8)",
                }}
                labelStyle={{ color: CHART_TICK, fontSize: "10px", marginBottom: "2px" }}
                formatter={(value) => [value, t("dashboard:trend.tooltip")]}
                cursor={{ stroke: CHART_COPPER, strokeWidth: 1, strokeOpacity: 0.4 }}
              />
              <Area
                type="monotone"
                dataKey="n"
                stroke={CHART_COPPER}
                strokeWidth={1.5}
                fill="url(#copperGrad)"
                dot={false}
                activeDot={{ r: 3, fill: CHART_COPPER, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ── Pipeline funnel ───────────────────────────────────────────────────────────

const PIPELINE_STATUSES = [
  ApplicationStatus.NEW,
  ApplicationStatus.APPROVED_BY_ADMIN,
  ApplicationStatus.HIRED,
  ApplicationStatus.REJECTED,
] as const;

function PipelineFunnel({ counts }: { counts: Record<string, number> | null }) {
  const { t } = useTranslation(["dashboard", "admin"]);

  const total = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : null;

  const pieData = counts
    ? PIPELINE_STATUSES.map((status) => ({ status, n: counts[status] ?? 0 })).filter(
        (d) => d.n > 0,
      )
    : null;

  return (
    <div className="rounded-xl border border-white/8 bg-card p-4">
      <Eyebrow>{t("dashboard:stats.statusBreakdown")}</Eyebrow>

      {counts == null ? (
        <div className="mt-3 space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="h-2.5 w-12 animate-pulse rounded bg-white/8" />
              <div className="h-2.5 flex-1 animate-pulse rounded bg-white/6" />
            </div>
          ))}
        </div>
      ) : total === 0 ? (
        <p className="mt-3 text-sm text-white/35">{t("dashboard:stats.noApplications")}</p>
      ) : (
        <div className="mt-4 flex items-center gap-4">
          {/* Donut chart */}
          <div dir="ltr" className="size-[72px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData ?? []}
                  dataKey="n"
                  innerRadius="52%"
                  outerRadius="100%"
                  paddingAngle={2}
                  startAngle={90}
                  endAngle={-270}
                  stroke="none"
                >
                  {(pieData ?? []).map((d) => (
                    <Cell key={d.status} fill={PIPELINE_FILL[d.status]} opacity={0.85} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Bar list with percentage labels */}
          <ol className="min-w-0 flex-1 space-y-2.5">
            {PIPELINE_STATUSES.map((status) => {
              const n = counts[status] ?? 0;
              const pct = total ? Math.round((n / total) * 100) : 0;
              const meta = APPLICATION_STATUS_META[status];
              return (
                <li key={status} className="flex items-center gap-2">
                  <span className={`size-2 shrink-0 rounded-full ${meta.dotClass}`} aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate text-xs text-white/50">
                    {t(`admin:applications.statusLabels.${status}`)}
                  </span>
                  <span className="shrink-0 text-[10px] tabular-nums text-white/35">
                    {pct}%
                  </span>
                  <span className="w-6 shrink-0 text-right text-xs font-medium tabular-nums text-white/70">
                    {n}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}

// ── Top jobs ──────────────────────────────────────────────────────────────────

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
      <Eyebrow>{t("dashboard:stats.topJobs")}</Eyebrow>
      {isLoading ? (
        <div className="mt-3 space-y-2.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="h-2.5 flex-1 animate-pulse rounded bg-white/8" />
              <div className="h-2.5 w-6 animate-pulse rounded bg-white/6" />
            </div>
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <p className="mt-3 text-sm text-white/35">{t("dashboard:stats.noTopJobs")}</p>
      ) : (
        <ol className="mt-3 space-y-2.5">
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
                      className="block h-1 rounded-full bg-copper/60 transition-all duration-500"
                      style={{
                        width: maxCount === 0 ? "0%" : `${(j.application_count / maxCount) * 100}%`,
                      }}
                    />
                  </span>
                </span>
                <span className="font-mono text-xs font-medium text-white/60 tabular-nums">
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

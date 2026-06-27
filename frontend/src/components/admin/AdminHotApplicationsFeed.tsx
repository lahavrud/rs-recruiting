import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import { getHotApplications } from "@/services/adminMatches";
import type { ApplicationWithDetails } from "@/types/candidates";

// ── Score ring (shared visual) ────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const r = 14;
  const circ = 2 * Math.PI * r;
  const colorCls =
    score >= 0.75
      ? "stroke-success"
      : score >= 0.55
        ? "stroke-copper"
        : "stroke-white/25";
  return (
    <svg
      viewBox="0 0 36 36"
      className="size-9 shrink-0 -rotate-90"
      aria-hidden="true"
    >
      <circle cx="18" cy="18" r={r} className="fill-none stroke-well" strokeWidth="2.5" />
      <circle
        cx="18"
        cy="18"
        r={r}
        className={`fill-none ${colorCls}`}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray={`${circ * score} ${circ}`}
      />
      <text
        x="18"
        y="19"
        textAnchor="middle"
        dominantBaseline="middle"
        className="rotate-90 fill-white/70 text-[8px] font-semibold tabular-nums"
        style={{ transformOrigin: "18px 18px" }}
      >
        {Math.round(score * 100)}
      </text>
    </svg>
  );
}

// ── Single hot-application row ────────────────────────────────────────────────

function HotApplicationRow({ app }: { app: ApplicationWithDetails }) {
  const navigate = useNavigate();
  const score = app.ai_score ?? 0;

  return (
    <li>
      <button
        type="button"
        onClick={() => navigate(`/admin/applications/${app.id}`)}
        className="group flex w-full items-center gap-3.5 border-b border-white/6 px-4 py-4 text-start last:border-0 transition-colors active:bg-card-raised md:gap-4 md:py-3.5 md:hover:bg-card-raised"
      >
        {/* Score */}
        <ScoreRing score={score} />

        {/* Candidate info */}
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-white/90">{app.candidate.full_name}</p>
          {/* Job shown inline on mobile; desktop has its own column */}
          <p className="mt-0.5 truncate text-xs text-white/50 md:hidden">
            {app.job.title}
            <span className="text-white/25"> · </span>
            {app.job.company_name}
          </p>
          {app.candidate.resume_summary ? (
            <p className="mt-0.5 truncate text-xs text-white/35">
              {app.candidate.resume_summary}
            </p>
          ) : (
            <p className="mt-0.5 truncate text-xs text-white/25">{app.candidate.email}</p>
          )}
        </div>

        {/* Desktop: arrow + separate job column + CTA label */}
        <span className="hidden md:block" aria-hidden="true">
          <ArrowIcon />
        </span>
        <div className="hidden min-w-0 w-52 shrink-0 md:block">
          <p className="truncate text-sm font-medium text-white/80">{app.job.title}</p>
          <p className="truncate text-xs text-white/40">{app.job.company_name}</p>
        </div>
        {/* Mobile: forward chevron tap hint */}
        <ChevronIcon />
      </button>
    </li>
  );
}

// ── Skeleton row ──────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <li className="flex items-center gap-3.5 border-b border-white/6 px-4 py-4 last:border-0 md:gap-4 md:py-3.5">
      <div className="size-9 shrink-0 animate-pulse rounded-full bg-white/8" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="h-3 w-32 animate-pulse rounded bg-white/8" />
        <div className="h-2.5 w-44 animate-pulse rounded bg-white/6 md:hidden" />
        <div className="h-2.5 w-48 animate-pulse rounded bg-white/6" />
      </div>
      <div className="hidden w-52 shrink-0 space-y-1.5 md:block">
        <div className="h-3 w-36 animate-pulse rounded bg-white/8" />
        <div className="h-2.5 w-24 animate-pulse rounded bg-white/6" />
      </div>
      <div className="size-4 shrink-0 animate-pulse rounded bg-white/6 md:hidden" />
    </li>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AdminHotApplicationsFeed() {
  const { t } = useTranslation("dashboard");
  const [apps, setApps] = useState<ApplicationWithDetails[] | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    getHotApplications(10, ctrl.signal)
      .then(setApps)
      .catch(() => setHasError(true));
    return () => ctrl.abort();
  }, []);

  return (
    <div>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <Eyebrow>{t("dashboard:matches.hotTitle")}</Eyebrow>
          <p className="mt-1 text-xs text-white/40">{t("dashboard:matches.hotSubtitle")}</p>
        </div>
        <FlameIcon />
      </div>

      <div className="overflow-hidden rounded-xl border border-white/8 bg-card">
        {hasError ? (
          <p className="px-4 py-5 text-sm text-danger/70">
            {t("dashboard:matches.hotLoadError")}
          </p>
        ) : apps == null ? (
          <ul>
            {[1, 2, 3].map((i) => (
              <SkeletonRow key={i} />
            ))}
          </ul>
        ) : apps.length === 0 ? (
          <p className="px-4 py-5 text-sm text-white/35">{t("dashboard:matches.hotEmpty")}</p>
        ) : (
          <ul>
            {apps.map((app) => (
              <HotApplicationRow key={app.id} app={app} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4 shrink-0 rotate-180 text-white/20 rtl:rotate-0"
      aria-hidden="true"
    >
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4 shrink-0 text-white/20 rtl:rotate-180 md:hidden"
      aria-hidden="true"
    >
      <path d="M6 3l5 5-5 5" />
    </svg>
  );
}

function FlameIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-5 shrink-0 text-copper/60"
      aria-hidden="true"
    >
      <path d="M12 2c0 0-4 4-4 8a4 4 0 0 0 8 0c0-1.5-.5-3-1.5-4.5C14 7 15 9 15 10a3 3 0 0 1-6 0c0-2.5 2-5 3-8Z" />
      <path d="M12 14a2 2 0 0 0 0 4 2 2 0 0 0 0-4Z" />
    </svg>
  );
}

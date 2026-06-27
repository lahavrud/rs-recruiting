import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import { getGlobalMatches, type GlobalMatchRead } from "@/services/adminMatches";

// ── Score ring ────────────────────────────────────────────────────────────────

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

// ── Score label ───────────────────────────────────────────────────────────────

function ScoreLabel({ score }: { score: number }) {
  const { t } = useTranslation("dashboard");
  if (score >= 0.75)
    return (
      <span className="rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold text-success">
        {t("dashboard:matches.scoreLabelExcellent")}
      </span>
    );
  if (score >= 0.55)
    return (
      <span className="rounded-full bg-copper/10 px-2 py-0.5 text-[10px] font-semibold text-copper">
        {t("dashboard:matches.scoreLabelGood")}
      </span>
    );
  return (
    <span className="rounded-full bg-white/6 px-2 py-0.5 text-[10px] font-medium text-white/35">
      {t("dashboard:matches.scoreLabelAverage")}
    </span>
  );
}

// ── Single match row ──────────────────────────────────────────────────────────

function MatchRow({ match }: { match: GlobalMatchRead }) {
  const navigate = useNavigate();

  return (
    <li>
      <button
        type="button"
        onClick={() =>
          navigate(`/admin/candidates/${match.candidate.id}?job=${match.job.id}`)
        }
        className="group flex w-full items-center gap-3.5 border-b border-white/6 px-4 py-4 text-start last:border-0 transition-colors active:bg-card-raised md:gap-4 md:py-3.5 md:hover:bg-card-raised"
      >
        <ScoreRing score={match.score} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate font-medium text-white/90">{match.candidate.full_name}</p>
            <ScoreLabel score={match.score} />
          </div>
          {/* Job shown inline on mobile; desktop has its own column */}
          <p className="mt-0.5 truncate text-xs text-white/50 md:hidden">
            {match.job.title}
            <span className="text-white/25"> · </span>
            {match.job.company_name}
          </p>
          {match.candidate.resume_summary ? (
            <p className="mt-0.5 truncate text-xs text-white/35">
              {match.candidate.resume_summary}
            </p>
          ) : (
            <p className="mt-0.5 truncate text-xs text-white/25">{match.candidate.email}</p>
          )}
        </div>

        {/* Desktop: arrow + separate job column */}
        <span className="hidden md:block" aria-hidden="true">
          <ArrowIcon />
        </span>
        <div className="hidden min-w-0 w-52 shrink-0 md:block">
          <p className="truncate text-sm font-medium text-white/80">{match.job.title}</p>
          <p className="truncate text-xs text-white/40">{match.job.company_name}</p>
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

export default function AdminMatchFeed() {
  const { t } = useTranslation("dashboard");
  const [matches, setMatches] = useState<GlobalMatchRead[] | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    getGlobalMatches(10, ctrl.signal)
      .then(setMatches)
      .catch(() => setHasError(true));
    return () => ctrl.abort();
  }, []);

  return (
    <div>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <Eyebrow>{t("dashboard:matches.title")}</Eyebrow>
          <p className="mt-1 text-xs text-white/40">{t("dashboard:matches.subtitle")}</p>
        </div>
        <SparkleIcon />
      </div>

      <div className="overflow-hidden rounded-xl border border-white/8 bg-card">
        {hasError ? (
          <p className="px-4 py-5 text-sm text-danger/70">
            {t("dashboard:matches.loadError")}
          </p>
        ) : matches == null ? (
          <ul>
            {[1, 2, 3, 4, 5].map((i) => (
              <SkeletonRow key={i} />
            ))}
          </ul>
        ) : matches.length === 0 ? (
          <p className="px-4 py-5 text-sm text-white/35">{t("dashboard:matches.empty")}</p>
        ) : (
          <ul>
            {matches.map((m) => (
              <MatchRow key={`${m.candidate.id}-${m.job.id}`} match={m} />
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

function SparkleIcon() {
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
      <path d="M12 3v1m0 16v1M4.22 4.22l.7.7m12.16 12.16.7.7M3 12h1m16 0h1M4.22 19.78l.7-.7M18.36 5.64l.7-.7" />
      <path d="M12 7a5 5 0 1 0 0 10A5 5 0 0 0 12 7Z" />
    </svg>
  );
}

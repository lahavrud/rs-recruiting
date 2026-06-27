import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import { useToast } from "@/hooks/useToast";
import {
  dismissMatch,
  getGlobalMatches,
  pushMatch,
  type GlobalMatchRead,
} from "@/services/adminMatches";

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

// ── Score badge (color label) ─────────────────────────────────────────────────

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

interface MatchRowProps {
  match: GlobalMatchRead;
  onPush: () => Promise<void>;
  onDismiss: () => Promise<void>;
}

function MatchRow({ match, onPush, onDismiss }: MatchRowProps) {
  const { t } = useTranslation("dashboard");
  const navigate = useNavigate();
  const [busy, setBusy] = useState<"push" | "dismiss" | null>(null);

  async function handlePush() {
    setBusy("push");
    try {
      await onPush();
    } finally {
      setBusy(null);
    }
  }

  async function handleDismiss() {
    setBusy("dismiss");
    try {
      await onDismiss();
    } finally {
      setBusy(null);
    }
  }

  return (
    <li className="group flex items-center gap-4 border-b border-white/6 px-4 py-3.5 last:border-0 transition-colors hover:bg-card-raised">
      {/* Score */}
      <ScoreRing score={match.score} />

      {/* Candidate */}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium text-white/90">{match.candidate.full_name}</p>
          <ScoreLabel score={match.score} />
        </div>
        {match.candidate.resume_summary ? (
          <p className="mt-0.5 truncate text-xs text-white/45">
            {match.candidate.resume_summary}
          </p>
        ) : (
          <p className="mt-0.5 truncate text-xs text-white/30">{match.candidate.email}</p>
        )}
        {/* Job title visible only when the job column is hidden */}
        <p className="mt-0.5 truncate text-xs text-white/30 md:hidden">
          {match.job.title} · {match.job.company_name}
        </p>
      </div>

      {/* Arrow — only makes sense alongside the job column */}
      <span className="hidden md:block" aria-hidden="true">
        <ArrowIcon />
      </span>

      {/* Job */}
      <div className="hidden min-w-0 w-52 shrink-0 md:block">
        <p className="truncate text-sm font-medium text-white/80">{match.job.title}</p>
        <p className="truncate text-xs text-white/40">{match.job.company_name}</p>
      </div>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-2">
        {/* Push — creates an application */}
        <Button
          variant="primary"
          size="sm"
          onClick={handlePush}
          disabled={busy !== null}
        >
          {busy === "push" ? "…" : t("dashboard:matches.push")}
        </Button>

        {/* Navigate to candidate */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(`/admin/candidates/${match.candidate.id}`)}
          className="hidden sm:inline-flex"
        >
          {t("dashboard:matches.viewCandidate")}
        </Button>

        {/* Dismiss — persisted to backend */}
        <Button
          variant="ghost"
          size="sm"
          onClick={handleDismiss}
          disabled={busy !== null}
          aria-label={t("dashboard:matches.dismiss")}
          className="px-1.5 py-1.5 text-white/20 hover:border-transparent hover:bg-white/6 hover:text-white/50"
        >
          {busy === "dismiss" ? "…" : <XIcon />}
        </Button>
      </div>
    </li>
  );
}

// ── Skeleton row ──────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <li className="flex items-center gap-4 border-b border-white/6 px-4 py-3.5 last:border-0">
      <div className="size-9 shrink-0 animate-pulse rounded-full bg-white/8" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="h-3 w-32 animate-pulse rounded bg-white/8" />
        <div className="h-2.5 w-48 animate-pulse rounded bg-white/6" />
      </div>
      <div className="hidden w-52 space-y-1.5 md:block">
        <div className="h-3 w-36 animate-pulse rounded bg-white/8" />
        <div className="h-2.5 w-24 animate-pulse rounded bg-white/6" />
      </div>
      <div className="h-7 w-20 animate-pulse rounded-lg bg-white/6" />
    </li>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AdminMatchFeed() {
  const { t } = useTranslation("dashboard");
  const toast = useToast();
  const [matches, setMatches] = useState<GlobalMatchRead[] | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    getGlobalMatches(10, ctrl.signal)
      .then(setMatches)
      .catch(() => setHasError(true));
    return () => ctrl.abort();
  }, []);

  function removeFromList(candidateId: number, jobId: number) {
    setMatches((prev) =>
      prev
        ? prev.filter((m) => !(m.candidate.id === candidateId && m.job.id === jobId))
        : prev,
    );
  }

  async function handlePush(candidateId: number, jobId: number, score: number) {
    try {
      await pushMatch(candidateId, jobId, score);
      removeFromList(candidateId, jobId);
    } catch (err: unknown) {
      const httpStatus = (err as { response?: { status?: number } })?.response?.status;
      if (httpStatus === 409) {
        toast.info(t("dashboard:matches.alreadyApplied"));
        removeFromList(candidateId, jobId);
      } else {
        toast.error(t("dashboard:matches.pushError"));
      }
    }
  }

  async function handleDismiss(candidateId: number, jobId: number, score: number) {
    try {
      await dismissMatch(candidateId, jobId, score);
      removeFromList(candidateId, jobId);
    } catch {
      toast.error(t("dashboard:matches.pushError"));
    }
  }

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
              <MatchRow
                key={`${m.candidate.id}-${m.job.id}`}
                match={m}
                onPush={() => handlePush(m.candidate.id, m.job.id, m.score)}
                onDismiss={() => handleDismiss(m.candidate.id, m.job.id, m.score)}
              />
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

function XIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      className="size-3.5"
      aria-hidden="true"
    >
      <path d="M3 3l10 10M13 3L3 13" />
    </svg>
  );
}

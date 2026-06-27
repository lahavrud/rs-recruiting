import { useTranslation } from "react-i18next";

import type { CompanyApplicationRead } from "@/types/companies";
import { formatDate } from "@/utils/formatDate";

const SCORE_THRESHOLDS = { high: 0.8, mid: 0.65 };
const PCT_MULTIPLIER = 100;

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * PCT_MULTIPLIER);
  const colorCls =
    pct >= SCORE_THRESHOLDS.high * PCT_MULTIPLIER
      ? "bg-success"
      : pct >= SCORE_THRESHOLDS.mid * PCT_MULTIPLIER
        ? "bg-copper"
        : "bg-warning";
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/8">
        <div className={`h-full rounded-full ${colorCls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-sm tabular-nums text-white/60">{pct}%</span>
    </div>
  );
}

interface CandidateDetailDrawerProps {
  app: CompanyApplicationRead | null;
  onClose: () => void;
}

export default function CandidateDetailDrawer({ app, onClose }: CandidateDetailDrawerProps) {
  const { t } = useTranslation("company");

  if (!app) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        className="fixed inset-y-0 start-0 z-50 flex w-80 flex-col border-e border-white/8 bg-card shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
          <h2 className="text-sm font-semibold text-white/85">
            {t("company:kanban.drawer.title")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-white/40 transition hover:text-white/80"
            aria-label={t("company:kanban.drawer.close")}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Name + contact */}
          <div className="space-y-1">
            <p className="text-base font-semibold text-white/90">
              {app.candidate.full_name}
            </p>
            <p className="text-sm text-white/50">{app.candidate.email}</p>
            {app.candidate.phone && (
              <p className="text-sm text-white/40" dir="ltr">
                {app.candidate.phone}
              </p>
            )}
          </div>

          {/* Applied date */}
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-copper mb-1">
              {t("company:kanban.drawer.appliedOn")}
            </p>
            <p className="text-sm text-white/55">{formatDate(app.created_at)}</p>
          </div>

          {/* Match score */}
          {app.match_score != null && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-copper mb-2">
                {t("company:kanban.drawer.matchScore")}
              </p>
              <ScoreBar score={app.match_score} />
            </div>
          )}

          {/* AI review */}
          {app.ai_review && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-copper mb-2">
                {t("company:kanban.drawer.aiReview")}
              </p>
              <p className="text-sm leading-relaxed text-white/70">{app.ai_review}</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

import { useEffect, useState } from "react";

import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import Eyebrow from "@/components/ui/Eyebrow";
import { PCT_MULTIPLIER, scoreBarColor } from "@/pages/company/components/scoreUtils";
import type { CompanyApplicationRead } from "@/types/companies";
import { formatDate } from "@/utils/formatDate";

const TRANSITION_MS = 300;

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * PCT_MULTIPLIER);
  const colorCls = scoreBarColor(pct);
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

  // displayApp persists the data through the exit animation.
  // isMounted gates DOM presence; isOpen drives the CSS transition.
  // All three update asynchronously (inside rAF / setTimeout) so they
  // never call setState synchronously inside the effect body.
  const [displayApp, setDisplayApp] = useState<CompanyApplicationRead | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (app) {
      let innerRaf = 0;
      const outerRaf = requestAnimationFrame(() => {
        setDisplayApp(app);
        setIsMounted(true);
        innerRaf = requestAnimationFrame(() => setIsOpen(true));
      });
      return () => {
        cancelAnimationFrame(outerRaf);
        cancelAnimationFrame(innerRaf);
      };
    }
    const closingRaf = requestAnimationFrame(() => setIsOpen(false));
    const timer = setTimeout(() => {
      setIsMounted(false);
      setDisplayApp(null);
    }, TRANSITION_MS);
    return () => {
      cancelAnimationFrame(closingRaf);
      clearTimeout(timer);
    };
  }, [app]);

  if (!isMounted || !displayApp) return null;

  return createPortal(
    <>
      {/* Backdrop — dims screen and closes on any outside interaction */}
      <div
        className={`fixed inset-0 z-40 bg-black/60 transition-opacity duration-300 ${
          isOpen ? "opacity-100 ease-out" : "opacity-0 ease-in"
        }`}
        onClick={onClose}
        onWheel={onClose}
        onTouchMove={onClose}
        aria-hidden="true"
      />

      {/* Drawer — slides in from the right (start edge in RTL) */}
      <div
        role="dialog"
        aria-modal="true"
        className={`fixed inset-y-0 start-0 z-50 flex w-80 flex-col border-e border-white/8 bg-card shadow-2xl transition-transform duration-300 ${
          isOpen ? "translate-x-0 ease-out" : "translate-x-full ease-in"
        }`}
      >
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

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <div className="space-y-1">
            <p className="text-base font-semibold text-white/90">
              {displayApp.candidate.full_name}
            </p>
            <p className="text-sm text-white/50">{displayApp.candidate.email}</p>
            {displayApp.candidate.phone && (
              <p className="text-sm text-white/40" dir="ltr">
                {displayApp.candidate.phone}
              </p>
            )}
          </div>

          <div>
            <Eyebrow className="mb-1">{t("company:kanban.drawer.appliedOn")}</Eyebrow>
            <p className="text-sm text-white/55">{formatDate(displayApp.created_at)}</p>
          </div>

          {displayApp.match_score != null && (
            <div>
              <Eyebrow className="mb-2">{t("company:kanban.drawer.matchScore")}</Eyebrow>
              <ScoreBar score={displayApp.match_score} />
            </div>
          )}

          {displayApp.ai_review && (
            <div>
              <Eyebrow className="mb-2">{t("company:kanban.drawer.aiReview")}</Eyebrow>
              <p className="text-sm leading-relaxed text-white/70">{displayApp.ai_review}</p>
            </div>
          )}
        </div>
      </div>
    </>,
    document.body,
  );
}

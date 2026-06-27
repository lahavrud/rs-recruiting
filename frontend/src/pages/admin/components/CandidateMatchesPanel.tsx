import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { MatchList, type MatchEntry } from "@/components/admin/MatchList";
import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import { useToast } from "@/hooks/useToast";
import { getCandidateJobMatches } from "@/services/adminCandidates";
import { dismissMatch, pushMatch } from "@/services/adminMatches";
import type { CandidateJobMatchRead } from "@/types/candidates";

interface Props {
  candidateId: number;
}

/** Matched jobs panel for the candidate record pane. */
export default function CandidateMatchesPanel({ candidateId }: Props) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [matches, setMatches] = useState<CandidateJobMatchRead[] | null>(null);
  const [hasError, setHasError] = useState(false);
  const [pushing, setPushing] = useState(false);

  const highlightedJobId = Number(searchParams.get("job")) || null;

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setMatches(null);
    setHasError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    const ctrl = new AbortController();
    getCandidateJobMatches(candidateId, ctrl.signal)
      .then(setMatches)
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setHasError(true);
      });
    return () => ctrl.abort();
  }, [candidateId]);

  const highlighted =
    highlightedJobId != null ? (matches?.find((m) => m.job.id === highlightedJobId) ?? null) : null;

  function clearJobParam() {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("job");
      return next;
    }, { replace: true });
  }

  async function handleDismiss() {
    if (!highlighted) return;
    try {
      await dismissMatch(candidateId, highlighted.job.id, highlighted.score);
    } catch {
      // Non-blocking — banner closes regardless; backend persist failure is tolerable
    }
    clearJobParam();
  }

  async function handlePush() {
    if (!highlighted) return;
    setPushing(true);
    try {
      await pushMatch(candidateId, highlighted.job.id, highlighted.score);
      toast.success(t("admin:candidates.pushSuccess"));
      clearJobParam();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        toast.info(t("admin:candidates.pushAlreadyApplied"));
        clearJobParam();
      } else {
        toast.error(t("admin:candidates.pushError"));
      }
    } finally {
      setPushing(false);
    }
  }

  const entries: MatchEntry[] | null =
    matches?.map((m) => ({
      key: m.job.id,
      name: m.job.title,
      meta: m.job.location,
      score: m.score,
      onClick: () => navigate(`/admin/jobs/${m.job.id}`),
    })) ?? null;

  return (
    <div>
      <Eyebrow>{t("admin:candidates.matchesSection")}</Eyebrow>

      {/* Push banner — shown when arriving from the AI match feed with ?job=N */}
      {highlighted && (
        <div className="mt-3 flex items-center gap-3 rounded-lg border border-copper/30 bg-copper/8 px-3.5 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-copper/90">{highlighted.job.title}</p>
            <p className="mt-0.5 truncate text-xs text-white/45">{highlighted.job.company_name}</p>
          </div>
          <Button size="sm" onClick={handlePush} disabled={pushing} className="shrink-0">
            {pushing ? "…" : t("admin:candidates.pushAction")}
          </Button>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label={t("admin:candidates.pushDismiss")}
            className="shrink-0 rounded p-0.5 text-white/25 transition hover:text-white/50"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className="size-3.5" aria-hidden="true">
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          </button>
        </div>
      )}

      <MatchList
        entries={entries}
        hasError={hasError}
        emptyMessage={t("admin:candidates.noMatches")}
        errorMessage={t("admin:candidates.matchesLoadError")}
      />
    </div>
  );
}

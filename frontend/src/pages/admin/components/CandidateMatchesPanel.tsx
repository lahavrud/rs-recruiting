import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { MatchList, type MatchEntry } from "@/components/admin/MatchList";
import Eyebrow from "@/components/ui/Eyebrow";
import { getCandidateJobMatches } from "@/services/adminCandidates";
import type { CandidateJobMatchRead } from "@/types/candidates";

interface Props {
  candidateId: number;
}

/** Matched jobs panel for the candidate record pane. */
export default function CandidateMatchesPanel({ candidateId }: Props) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const [matches, setMatches] = useState<CandidateJobMatchRead[] | null>(null);
  const [hasError, setHasError] = useState(false);

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
      <MatchList
        entries={entries}
        hasError={hasError}
        emptyMessage={t("admin:candidates.noMatches")}
        errorMessage={t("admin:candidates.matchesLoadError")}
      />
    </div>
  );
}

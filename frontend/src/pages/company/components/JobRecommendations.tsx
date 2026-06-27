import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import { PCT_MULTIPLIER, scoreBarColor } from "@/pages/company/components/scoreUtils";
import api from "@/services/api";
import type { CompanyJobRecommendationRead } from "@/types/companies";

interface JobRecommendationsProps {
  jobId: number;
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * PCT_MULTIPLIER);
  const colorCls = scoreBarColor(pct);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/8">
        <div className={`h-full rounded-full ${colorCls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] tabular-nums text-white/45">{pct}%</span>
    </div>
  );
}

export default function JobRecommendations({ jobId }: JobRecommendationsProps) {
  const { t } = useTranslation("company");
  const [recs, setRecs] = useState<CompanyJobRecommendationRead[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<CompanyJobRecommendationRead[]>(`/api/jobs/${jobId}/recommendations`)
      .then((r) => {
        if (!cancelled) setRecs(r.data);
      })
      .catch(() => {
        if (!cancelled) setRecs([]);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (recs === null) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-card" />
        ))}
      </div>
    );
  }

  if (recs.length === 0) {
    return <p className="text-sm text-white/30">{t("company:jobs.kanban.aiEmpty")}</p>;
  }

  return (
    <div className="space-y-2">
      {recs.map((rec) => (
        <div
          key={rec.candidate_id}
          className="flex items-start justify-between gap-3 rounded-lg border border-white/8 bg-card-raised p-3"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white/85">{rec.full_name}</p>
            <p className="truncate text-xs text-white/40">{rec.email}</p>
          </div>
          <ScoreBar score={rec.score} />
        </div>
      ))}
    </div>
  );
}

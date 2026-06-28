import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import ActivityTimeline from "@/components/admin/ActivityTimeline";
import Eyebrow from "@/components/ui/Eyebrow";
import { getCandidateActivity } from "@/services/adminCandidates";
import type { CandidateActivityEvent } from "@/types/audit";

const SKELETON_ROWS = 3;

function ActivityTimelineSkeleton() {
  return (
    <ul className="mt-3 space-y-4" aria-hidden>
      {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
        <li key={i} className="relative animate-pulse ps-5">
          <span className="absolute start-0 top-1.5 size-1.5 rounded-full bg-white/10" />
          <div className="h-3.5 w-3/4 rounded bg-white/8" />
          <div className="mt-1.5 h-3 w-1/4 rounded bg-white/5" />
        </li>
      ))}
    </ul>
  );
}

import StatusChangeBadges from "./StatusChangeBadges";

interface Props {
  candidateId: number;
}

const ACTIVITY_LIMIT = 50;

/** Activity timeline panel for the candidate record pane. */
export default function CandidateActivityPanel({ candidateId }: Props) {
  const { t } = useTranslation('admin');
  const [events, setEvents] = useState<CandidateActivityEvent[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setEvents(null);
    setError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    const ctrl = new AbortController();
    getCandidateActivity(candidateId, { limit: ACTIVITY_LIMIT }, ctrl.signal)
      .then((page) => setEvents(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setError(true);
      });
    return () => ctrl.abort();
  }, [candidateId]);

  function describeEvent(event: CandidateActivityEvent): string {
    switch (event.action) {
      case "candidate.consent":
        return t("admin:candidates.activity.actions.consent");
      case "candidate.terms_accept":
        return t("admin:candidates.activity.actions.termsAccept");
      case "candidate_register_via_apply":
        return t("admin:candidates.activity.actions.registerViaApply");
      case "candidate.delete":
        return t("admin:candidates.activity.actions.delete");
      case "candidate.purge":
        return t("admin:candidates.activity.actions.purge");
      default:
        return event.action;
    }
  }

  return (
    <div>
      <Eyebrow>{t("admin:candidates.activitySection")}</Eyebrow>

      <ActivityTimeline
        events={events}
        error={error}
        loadingSlot={<ActivityTimelineSkeleton />}
        errorMessage={t("admin:candidates.errors.activityLoadFailed")}
        emptyMessage={t("admin:candidates.activityEmpty")}
        renderItem={(event) =>
          event.action === "application.status_change" ? (
            <>
              {event.job_title && <p className="text-xs text-white/60">{event.job_title}</p>}
              <div className="mt-1">
                <StatusChangeBadges detail={event.detail} />
              </div>
            </>
          ) : (
            <p className="text-sm text-white/75">{describeEvent(event)}</p>
          )
        }
      />
    </div>
  );
}

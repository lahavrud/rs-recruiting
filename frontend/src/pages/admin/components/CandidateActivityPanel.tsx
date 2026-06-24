import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Eyebrow from "@/components/ui/Eyebrow";
import StatusBadge from "@/components/ui/StatusBadge";
import { getCandidateActivity } from "@/services/adminCandidates";
import type { CandidateActivityEvent } from "@/types/audit";
import { formatDate } from "@/utils/formatDate";

interface Props {
  candidateId: number;
}

const ACTIVITY_LIMIT = 50;

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-copper/10 text-copper",
  APPROVED_BY_ADMIN: "bg-success/10 text-success",
  REJECTED: "bg-danger/10 text-danger",
  HIRED: "bg-hired/10 text-hired",
  JOB_CLOSED: "bg-white/8 text-white/45",
  WITHDRAWN: "bg-white/3 text-white/25",
};

/** Activity timeline panel for the candidate record pane. */
export default function CandidateActivityPanel({ candidateId }: Props) {
  const { t } = useTranslation(['admin', 'common']);
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

      {error ? (
        <p className="mt-3 text-xs text-danger">
          {t("admin:candidates.errors.activityLoadFailed")}
        </p>
      ) : events == null ? (
        <p className="mt-3 text-xs text-white/35">{t("common:loading")}</p>
      ) : events.length === 0 ? (
        <p className="mt-3 text-xs text-white/35">{t("admin:candidates.activityEmpty")}</p>
      ) : (
        <ul className="mt-3 space-y-4">
          {events.map((event, i) => {
            const [statusFrom, statusTo] = (event.detail ?? "").split("->");
            return (
              <li key={event.id} className="relative ps-5">
                {i < events.length - 1 && (
                  <span
                    className="absolute start-[3px] top-3 h-full w-px bg-white/8"
                    aria-hidden
                  />
                )}
                <span
                  className="absolute start-0 top-1.5 size-1.5 rounded-full bg-copper/60"
                  aria-hidden
                />
                {event.action === "application.status_change" ? (
                  <>
                    {event.job_title && (
                      <p className="text-xs text-white/60">{event.job_title}</p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <StatusBadge
                        label={t(`admin:applications.statusLabels.${statusFrom}`, statusFrom)}
                        colorCls={STATUS_COLORS[statusFrom] ?? "bg-white/8 text-white/45"}
                      />
                      <span className="text-white/30" aria-hidden>
                        ←
                      </span>
                      <StatusBadge
                        label={t(`admin:applications.statusLabels.${statusTo}`, statusTo)}
                        colorCls={STATUS_COLORS[statusTo] ?? "bg-white/8 text-white/45"}
                      />
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-white/75">{describeEvent(event)}</p>
                )}
                <p className="mt-1 text-xs text-white/35">{formatDate(event.created_at)}</p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

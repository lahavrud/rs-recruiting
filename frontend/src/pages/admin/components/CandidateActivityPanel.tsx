import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { getCandidateActivity } from "@/services/adminCandidates";
import type { AuditLogRead } from "@/types/api";
import Eyebrow from "@/components/ui/Eyebrow";
import { formatDate } from "@/utils/formatDate";

interface Props {
  candidateId: number;
}

const ACTIVITY_LIMIT = 50;

/** Activity timeline panel for the candidate record pane. */
export default function CandidateActivityPanel({ candidateId }: Props) {
  const { t } = useTranslation(['admin', 'common']);
  const [events, setEvents] = useState<AuditLogRead[] | null>(null);
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

  function describeEvent(event: AuditLogRead): string {
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
      case "application.status_change": {
        const [from, to] = (event.detail ?? "").split("->");
        return t("admin:candidates.activity.statusChange", {
          from: t(`admin:applications.statusLabels.${from}`, from),
          to: t(`admin:applications.statusLabels.${to}`, to),
        });
      }
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
          {events.map((event, i) => (
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
              <p className="text-sm text-white/75">{describeEvent(event)}</p>
              <p className="mt-0.5 text-xs text-white/35">{formatDate(event.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

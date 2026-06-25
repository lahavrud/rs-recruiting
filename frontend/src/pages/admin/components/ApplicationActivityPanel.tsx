import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import ActivityTimeline from "@/components/admin/ActivityTimeline";
import Eyebrow from "@/components/ui/Eyebrow";
import { getApplicationActivity } from "@/services/adminApplications";
import type { AuditLogRead } from "@/types/audit";

import StatusChangeBadges from "./StatusChangeBadges";

interface Props {
  applicationId: number;
}

const ACTIVITY_LIMIT = 50;

/** Activity timeline panel for the application record pane. */
export default function ApplicationActivityPanel({ applicationId }: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const [events, setEvents] = useState<AuditLogRead[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setEvents(null);
    setError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    const ctrl = new AbortController();
    getApplicationActivity(applicationId, { limit: ACTIVITY_LIMIT }, ctrl.signal)
      .then((page) => setEvents(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setError(true);
      });
    return () => ctrl.abort();
  }, [applicationId]);

  function describeEvent(event: AuditLogRead): string {
    switch (event.action) {
      case "application.submitted":
        return t("admin:applications.activity.actions.submitted");
      default:
        return event.action;
    }
  }

  return (
    <div>
      <Eyebrow>{t("admin:applications.activitySection")}</Eyebrow>

      <ActivityTimeline
        events={events}
        error={error}
        loadingMessage={t("common:loading")}
        errorMessage={t("admin:applications.errors.activityLoadFailed")}
        emptyMessage={t("admin:applications.activityEmpty")}
        renderItem={(event) =>
          event.action === "application.status_change" ? (
            <StatusChangeBadges detail={event.detail} />
          ) : (
            <p className="text-sm text-white/75">{describeEvent(event)}</p>
          )
        }
      />
    </div>
  );
}

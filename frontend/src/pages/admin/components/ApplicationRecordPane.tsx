import { useTranslation } from "react-i18next";

import RecordPane from "@/components/admin/RecordPane";
import { getApplication } from "@/services/adminApplications";
import type { ApplicationWithDetails } from "@/types/candidates";

interface Props {
  applicationId: number | null;
  application?: ApplicationWithDetails;
}

/** Right-hand record pane: breadcrumb + candidate/job context. Composes the shared `RecordPane` shell — header, relations, and timeline land in follow-up slices. */
export default function ApplicationRecordPane({ applicationId, application }: Props) {
  const { t } = useTranslation(["admin", "common"]);

  return (
    <RecordPane
      id={applicationId}
      entity={application}
      fetcher={getApplication}
      listPath="/admin/applications"
      listLabel={t("admin:applications.title")}
      crumbLabel={(app) => `${app.candidate.full_name} → ${app.job.title}`}
      emptyHeadline={t("admin:applications.record.emptyHeadline")}
      emptyDescription={t("admin:applications.record.emptyDescription")}
      notFoundHeadline={t("admin:applications.record.notFound")}
      loadErrorMessage={t("admin:applications.loadError")}
    >
      {(app) => (
        <>
          <h2 className="text-lg font-semibold text-white/90">{app.candidate.full_name}</h2>
          <p className="mt-1 text-sm text-white/50">{app.job.title}</p>

          <div className="mt-6 border-t border-white/8 pt-6">
            <p className="text-sm text-white/35">{t("admin:applications.record.comingSoon")}</p>
          </div>
        </>
      )}
    </RecordPane>
  );
}

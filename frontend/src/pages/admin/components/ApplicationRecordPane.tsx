import { useTranslation } from "react-i18next";

import RecordPane from "@/components/admin/RecordPane";
import { getApplication } from "@/services/adminApplications";
import type { ApplicationWithDetails } from "@/types/candidates";

import ApplicationActivityPanel from "./ApplicationActivityPanel";
import ApplicationRecordHeader from "./ApplicationRecordHeader";

type AppPatch = Pick<ApplicationWithDetails, "id"> &
  Partial<Pick<ApplicationWithDetails, "status" | "admin_notes" | "updated_at">>;

interface Props {
  applicationId: number | null;
  application?: ApplicationWithDetails;
  onUpdated: (patch: AppPatch) => void;
}

/** Right-hand record pane: breadcrumb + candidate/job context + inline status/notes + activity timeline. Composes the shared `RecordPane` shell — relations land in a follow-up slice. */
export default function ApplicationRecordPane({ applicationId, application, onUpdated }: Props) {
  const { t } = useTranslation(["admin", "common"]);

  return (
    <RecordPane
      id={applicationId}
      entity={application}
      fetcher={getApplication}
      listPath="/admin/applications"
      listLabel={t("admin:applications.title")}
      crumbLabel={(app) => (
        <span className="inline-flex items-center gap-2">
          <span className="text-white/85">{app.candidate.full_name}</span>
          <span aria-hidden="true" className="text-white/20">
            |
          </span>
          <span className="text-white/50">{app.job.title}</span>
        </span>
      )}
      emptyHeadline={t("admin:applications.record.emptyHeadline")}
      emptyDescription={t("admin:applications.record.emptyDescription")}
      notFoundHeadline={t("admin:applications.record.notFound")}
      loadErrorMessage={t("admin:applications.loadError")}
    >
      {(app) => (
        <>
          <ApplicationRecordHeader application={app} onUpdated={onUpdated} />
          <div className="mt-6 border-t border-white/8 pt-6">
            <ApplicationActivityPanel applicationId={app.id} />
          </div>
        </>
      )}
    </RecordPane>
  );
}

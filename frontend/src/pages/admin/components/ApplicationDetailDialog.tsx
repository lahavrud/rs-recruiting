import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Eyebrow from "@/components/ui/Eyebrow";
import ResumeButton from "@/components/ui/ResumeViewer";
import { type ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";
import { sanitizeLinkedInUrl } from "@/utils/validators";

interface DetailProps {
  app: ApplicationWithDetails | null;
  onClose: () => void;
  onUpdateStatus: () => void;
  onEditNotes: () => void;
  onDelete: () => void;
}

export default function ApplicationDetailDialog({
  app,
  onClose,
  onUpdateStatus,
  onEditNotes,
  onDelete,
}: DetailProps) {
  const { t } = useTranslation(["admin", "common"]);
  if (!app) return null;
  const c = app.candidate;
  const isWithdrawn = app.status === ApplicationStatus.WITHDRAWN;
  return (
    <Dialog
      open={app != null}
      onOpenChange={(o) => !o && onClose()}
      title={c.full_name}
      description={app.job.title}
      size="lg"
      footer={
        <>
          <Button variant="danger" onClick={onDelete}>
            {t("admin:applications.deleteAction")}
          </Button>
          <Button variant="ghost" onClick={onEditNotes}>
            {t("admin:applications.editNotesAction")}
          </Button>
          {!isWithdrawn && (
            <Button onClick={onUpdateStatus}>
              {t("admin:applications.updateStatusAction")}
            </Button>
          )}
        </>
      }
    >
      <ApplicationDetailBody app={app} onLeavePage={onClose} />
    </Dialog>
  );
}

/** Detail body shared by the desktop dialog and the mobile inline expansion. */
export function ApplicationDetailBody({
  app,
  onLeavePage,
}: {
  app: ApplicationWithDetails;
  onLeavePage?: () => void;
}) {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const c = app.candidate;
  const linkBtnCls =
    "inline-flex items-center rounded-sm border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-copper/90 transition hover:border-copper/30 hover:bg-copper/10 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 sm:text-copper/80 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline";
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-2 border-b border-white/8 pb-3">
        <button
          type="button"
          onClick={() => {
            onLeavePage?.();
            navigate(`/admin/candidates?detail=${app.candidate_id}`);
          }}
          className={linkBtnCls}
        >
          {t("common:viewCandidate")}
        </button>
        <button
          type="button"
          onClick={() => {
            onLeavePage?.();
            navigate(`/admin/jobs?detail=${app.job_id}`);
          }}
          className={linkBtnCls}
        >
          {t("common:viewJob")}
        </button>
        <span className="text-xs text-white/40">{formatDate(app.created_at)}</span>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span className="text-white/60">{c.email}</span>
        {c.phone && <span className="text-white/60">{c.phone}</span>}
        {c.linkedin_url && (
          <a
            href={sanitizeLinkedInUrl(c.linkedin_url)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-copper hover:text-gold"
          >
            {t("admin:applications.details.linkedin")} ↗
          </a>
        )}
        {c.resume_path ? (
          <ResumeButton
            resumePath={c.resume_path}
            candidateName={c.full_name}
            label={t("admin:applications.details.resume")}
          />
        ) : (
          <span className="text-white/40">
            {t("admin:applications.details.resume")}:{" "}
            {t("admin:applications.details.noFile")}
          </span>
        )}
      </div>

      {(app.service_concept ||
        app.salary_expectations ||
        app.strength ||
        app.growth_area) && (
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
          {app.service_concept && (
            <>
              <dt className="text-white/35">
                {t("admin:applications.details.serviceConcept")}
              </dt>
              <dd className="text-white/70">{app.service_concept}</dd>
            </>
          )}
          {app.salary_expectations && (
            <>
              <dt className="text-white/35">
                {t("admin:applications.details.salaryExpectations")}
              </dt>
              <dd className="text-white/70">{app.salary_expectations}</dd>
            </>
          )}
          {app.strength && (
            <>
              <dt className="text-white/35">
                {t("admin:applications.details.strength")}
              </dt>
              <dd className="text-white/70">{app.strength}</dd>
            </>
          )}
          {app.growth_area && (
            <>
              <dt className="text-white/35">
                {t("admin:applications.details.weakness")}
              </dt>
              <dd className="text-white/70">{app.growth_area}</dd>
            </>
          )}
        </dl>
      )}

      {app.admin_notes && (
        <div className="rounded-md border border-white/8 bg-card p-3 text-white/70">
          <Eyebrow>{t("admin:applications.modal.adminNotes")}</Eyebrow>
          <p className="mt-1 whitespace-pre-wrap">{app.admin_notes}</p>
        </div>
      )}
    </div>
  );
}

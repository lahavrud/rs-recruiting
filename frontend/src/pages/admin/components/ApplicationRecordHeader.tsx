import { useEffect, useRef, useState, type ReactNode } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import StatusSegmentedControl from "@/components/admin/StatusSegmentedControl";
import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import ResumeButton from "@/components/ui/ResumeViewer";
import { useToast } from "@/hooks/useToast";
import { updateApplicationNotes, updateApplicationStatus } from "@/services/adminApplications";
import { TEXTAREA_CLS } from "@/styles/forms";
import type { ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";
import { sanitizeLinkedInUrl } from "@/utils/validators";

import ApplicationAnswerFields from "./ApplicationAnswerFields";
import { ALL_STATUSES, APPLICATION_STATUS_SEGMENT_CONFIG, TERMINAL_STATUSES } from "./applicationStatusOptions";
import { IconArrowRight } from "./TriageIcons";

type AppPatch = Pick<ApplicationWithDetails, "id"> &
  Partial<Pick<ApplicationWithDetails, "status" | "admin_notes" | "updated_at">>;

interface Props {
  application: ApplicationWithDetails;
  onUpdated: (patch: AppPatch) => void;
}

/** Record-page header: identity, status-change, and notes — folds the old status/notes dialogs in as inline actions. */
export default function ApplicationRecordHeader({ application: app, onUpdated }: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const toast = useToast();
  const navigate = useNavigate();

  const [statusDraft, setStatusDraft] = useState(app.status);
  const [notesDraft, setNotesDraft] = useState(app.admin_notes ?? "");
  const [isSavingStatus, setIsSavingStatus] = useState(false);
  const [isSavingNotes, setIsSavingNotes] = useState(false);

  // Re-seed drafts only when navigating to a different application, not on every patch.
  const lastAppId = useRef<number | null>(null);
  useEffect(() => {
    if (lastAppId.current === app.id) return;
    lastAppId.current = app.id;
    setStatusDraft(app.status);
    setNotesDraft(app.admin_notes ?? "");
  }, [app.id, app.status, app.admin_notes]);

  const isWithdrawn = app.status === ApplicationStatus.WITHDRAWN;
  const isRevert = TERMINAL_STATUSES.has(app.status) && statusDraft !== app.status;
  const isNewRejection =
    statusDraft === ApplicationStatus.REJECTED && app.status !== ApplicationStatus.REJECTED;
  const notesDirty = notesDraft.trim() !== (app.admin_notes ?? "").trim();

  async function handleSaveStatus() {
    setIsSavingStatus(true);
    try {
      const updated = await updateApplicationStatus(app.id, {
        status: statusDraft as ApplicationWithDetails["status"],
        admin_notes: null,
      });
      onUpdated({ id: app.id, status: updated.status, updated_at: updated.updated_at });
      toast.success(t("admin:applications.savedToast"));
    } catch {
      toast.error(t("admin:applications.errors.updateFailed"));
    } finally {
      setIsSavingStatus(false);
    }
  }

  async function handleSaveNotes() {
    setIsSavingNotes(true);
    try {
      const updated = await updateApplicationNotes(app.id, notesDraft.trim() || null);
      onUpdated({
        id: app.id,
        admin_notes: updated.admin_notes,
        updated_at: updated.updated_at,
      });
      toast.success(t("admin:applications.notesSavedToast"));
    } catch {
      toast.error(t("admin:applications.errors.notesFailed"));
    } finally {
      setIsSavingNotes(false);
    }
  }

  const c = app.candidate;

  return (
    <div className="space-y-6">
      <Eyebrow>{t("admin:applications.record.eyebrow")}</Eyebrow>

      <div className="relative grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-x-3">
        {/* Connector — a line threading the two cards together, broken by a centered badge. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 hidden items-center justify-center sm:flex"
        >
          <span className="h-px w-full bg-copper/15" />
        </div>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-1/2 hidden -translate-x-1/2 -translate-y-1/2 sm:flex"
        >
          <span className="flex size-7 items-center justify-center rounded-full border border-copper/25 bg-card">
            <span className="size-2 rotate-45 bg-copper/70" />
          </span>
        </div>

        <EntityLinkCard onClick={() => navigate(`/admin/candidates/${app.candidate_id}`)}>
          <p className="text-base font-medium text-white/90">{c.full_name}</p>
          <div
            onClick={(e) => e.stopPropagation()}
            className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs"
          >
            <a
              href={`mailto:${c.email}`}
              className="text-copper/85 transition hover:text-copper hover:underline"
            >
              {c.email}
            </a>
            {c.phone && <span className="text-white/50">{c.phone}</span>}
            {c.linkedin_url && (
              <a
                href={sanitizeLinkedInUrl(c.linkedin_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-copper transition hover:text-gold"
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
              <span className="text-white/35">
                {t("admin:applications.details.resume")}: {t("admin:applications.details.noFile")}
              </span>
            )}
          </div>
        </EntityLinkCard>

        <div aria-hidden="true" className="flex flex-col items-center sm:hidden">
          <span className="h-2 w-px bg-copper/15" />
          <span className="flex size-6 items-center justify-center rounded-full border border-copper/25 bg-card">
            <span className="size-1.5 rotate-45 bg-copper/70" />
          </span>
          <span className="h-2 w-px bg-copper/15" />
        </div>

        <EntityLinkCard onClick={() => navigate(`/admin/jobs?detail=${app.job_id}`)}>
          <p className="text-base font-medium text-white/90">{app.job.title}</p>
          <p className="mt-2 text-xs text-white/50">{app.job.location}</p>
          <p className="mt-0.5 text-[11px] text-white/35">
            {t("admin:applications.record.appliedAt")} {formatDate(app.created_at)}
          </p>
        </EntityLinkCard>
      </div>

      <div className="border-t border-white/8 pt-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[14rem] flex-1">
            <label className="block text-xs text-white/50">
              {t("admin:applications.table.status")}
            </label>
            {isWithdrawn ? (
              <p className="mt-1.5 text-sm text-white/50">
                {t(`admin:applications.statusLabels.${app.status}`)}
              </p>
            ) : (
              <StatusSegmentedControl
                statuses={ALL_STATUSES}
                value={statusDraft}
                onChange={setStatusDraft}
                config={APPLICATION_STATUS_SEGMENT_CONFIG}
                labelFor={(s) => t(`admin:applications.statusLabels.${s}`)}
                ariaLabel={t("admin:applications.table.status")}
              />
            )}
          </div>
          {!isWithdrawn && (
            <Button
              size="sm"
              onClick={handleSaveStatus}
              disabled={isSavingStatus || statusDraft === app.status}
            >
              {isSavingStatus ? t("common:saving") : t("common:save")}
            </Button>
          )}
        </div>

        {isRevert && (
          <div className="mt-3 rounded-sm bg-warning/8 px-2.5 py-2 text-[11px] leading-relaxed">
            <p className="font-medium text-warning/85">{t("admin:applications.revertConfirm")}</p>
          </div>
        )}
        {isNewRejection && (
          <p className="mt-3 rounded-sm bg-info/5 px-2 py-1 text-[11px] leading-relaxed text-info/55">
            {t("admin:applications.record.notifyRejectionHint")}
          </p>
        )}
      </div>

      <div className="border-t border-white/8 pt-4">
        <label className="block text-xs text-white/50">
          {t("admin:applications.modal.adminNotes")}
        </label>
        <textarea
          value={notesDraft}
          onChange={(e) => setNotesDraft(e.target.value)}
          rows={3}
          maxLength={5000}
          className={`mt-1.5 ${TEXTAREA_CLS}`}
          placeholder={t("admin:applications.modal.notesPlaceholder")}
        />
        <div className="mt-2 flex items-center justify-end gap-2">
          {notesDraft.length > 4800 && (
            <span className="text-xs text-white/35">{notesDraft.length} / 5000</span>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={handleSaveNotes}
            disabled={isSavingNotes || !notesDirty}
          >
            {isSavingNotes ? t("common:saving") : t("common:save")}
          </Button>
        </div>
      </div>

      <ApplicationAnswerFields app={app} />

      <p className="border-t border-white/8 pt-4 text-sm text-white/35">
        {t("admin:applications.record.relationsComingSoon")}
      </p>
    </div>
  );
}

/** Identity card for a related entity (candidate/job) — the whole card navigates; nested interactive children stop propagation. */
function EntityLinkCard({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClick}
      className="group relative cursor-pointer rounded-xl border border-white/8 bg-card-raised p-4 pe-10 transition hover:border-white/15 hover:bg-card active:scale-[0.99]"
    >
      {children}
      <IconArrowRight
        className="absolute end-3 top-1/2 size-4 -translate-y-1/2 -scale-x-100 text-white/25 transition group-hover:text-copper"
      />
    </div>
  );
}

import { useEffect, useRef, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import { updateApplicationStatus } from "@/services/adminApplications";
import { SELECT_CLS, TEXTAREA_CLS } from "@/styles/forms";
import type { ApplicationStatusUpdate, ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";

import { ALL_STATUSES, TERMINAL_STATUSES } from "./applicationStatusOptions";

interface StatusDialogProps {
  app: ApplicationWithDetails | null;
  onClose: () => void;
  onSaved: (next: {
    id: number;
    status: ApplicationStatus;
    admin_notes: string | null;
    updated_at: string;
  }) => void;
  onError: () => void;
}

export default function ApplicationStatusDialog({
  app,
  onClose,
  onSaved,
  onError,
}: StatusDialogProps) {
  const { t } = useTranslation(["admin", "common"]);
  const [newStatus, setNewStatus] = useState<string>(
    app?.status ?? ApplicationStatus.NEW,
  );
  const [notes, setNotes] = useState<string>(app?.admin_notes ?? "");
  const [isSaving, setIsSaving] = useState(false);

  // Re-seed form fields whenever the target application changes.
  const lastAppId = useRef<number | null>(null);
  useEffect(() => {
    if (!app) {
      lastAppId.current = null;
      return;
    }
    if (lastAppId.current === app.id) return;
    lastAppId.current = app.id;
    setNewStatus(app.status);
    setNotes(app.admin_notes ?? "");
  }, [app]);

  async function handleSave() {
    if (!app) return;
    setIsSaving(true);
    const body: ApplicationStatusUpdate = {
      status: newStatus as ApplicationStatusUpdate["status"],
      admin_notes: notes.trim() || null,
    };
    try {
      const updated = await updateApplicationStatus(app.id, body);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setIsSaving(false);
    }
  }

  const isRevert =
    app != null && TERMINAL_STATUSES.has(app.status) && newStatus !== app.status;

  if (!app) return null;

  return (
    <Dialog
      open={app != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin:applications.modal.title")}
      size="md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSaving}>
            {t("common:cancel")}
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? t("common:saving") : t("common:save")}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-sm text-white/70">
        <p>
          <span className="text-white/40">
            {t("admin:applications.modal.candidateLabel")}:
          </span>{" "}
          {app.candidate.full_name}
        </p>
        <p>
          <span className="text-white/40">
            {t("admin:applications.modal.jobLabel")}:
          </span>{" "}
          {app.job.title}
        </p>
        <div>
          <label className="block text-white/50">
            {t("admin:applications.modal.newStatusLabel")}
          </label>
          <select
            value={newStatus}
            onChange={(e) => setNewStatus(e.target.value)}
            className={`mt-1 ${SELECT_CLS}`}
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s} className="bg-well">
                {t(`admin:applications.statusLabels.${s}`)}
              </option>
            ))}
          </select>
          {isRevert && (
            <p className="mt-2 text-xs text-warning">
              {t("admin:applications.revertConfirm")}
            </p>
          )}
        </div>
        <div>
          <label className="block text-white/50">
            {t("admin:applications.modal.adminNotes")}{" "}
            <span className="text-white/25">({t("common:optional")})</span>
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className={`mt-1 ${TEXTAREA_CLS}`}
            placeholder={t("admin:applications.modal.notesPlaceholder")}
          />
        </div>
      </div>
    </Dialog>
  );
}

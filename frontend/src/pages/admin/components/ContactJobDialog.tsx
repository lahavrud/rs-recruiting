import { useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import { useToast } from "@/hooks/useToast";
import { contactJob } from "@/services/adminJobs";
import { TEXTAREA_CLS } from "@/styles/forms";
import type { JobRead } from "@/types/jobs";

interface Props {
  job: JobRead | null;
  companyName?: string;
  onClose: () => void;
}

export default function ContactJobDialog({ job, companyName, onClose }: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const toast = useToast();
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);

  function handleClose() {
    setNote("");
    onClose();
  }

  async function handleSend() {
    if (!job) return;
    setSending(true);
    try {
      await contactJob(job.id, note);
      toast.success(t("admin:jobs.contactDialog.successToast"));
      handleClose();
    } catch {
      toast.error(t("admin:jobs.contactDialog.errorToast"));
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog
      open={job != null}
      onOpenChange={(o) => !o && handleClose()}
      title={t("admin:jobs.contactDialog.title")}
    >
      {job && (
        <div className="space-y-4">
          <p className="text-sm text-white/60">
            {companyName ?? job.company_name} — {job.title}
          </p>
          <div>
            <label
              htmlFor="contact-note"
              className="mb-1.5 block text-xs font-medium text-white/50"
            >
              {t("admin:jobs.contactDialog.noteLabel")}
            </label>
            <textarea
              id="contact-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder={t("admin:jobs.contactDialog.notePlaceholder")}
              className={TEXTAREA_CLS}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={handleClose} disabled={sending}>
              {t("common:cancel")}
            </Button>
            <Button size="sm" onClick={handleSend} disabled={sending}>
              {sending ? t("admin:jobs.contactDialog.sendingButton") : t("admin:jobs.contactDialog.sendButton")}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

import { useState } from "react";

import { useTranslation } from "react-i18next";

import AutoGrowTextarea from "@/components/ui/AutoGrowTextarea";
import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import Dialog from "@/components/ui/Dialog";
import { useConfirmableClose } from "@/hooks/useConfirmableClose";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import { updateJob } from "@/services/adminJobs";
import { JOB_REQ_MIN_COUNT, JobStatus } from "@/types/api";
import type { JobAdminUpdate, JobRead } from "@/types/api";
import { focusFirstError } from "@/utils/focusFirstError";
import { isDirtyByJSON } from "@/utils/isDirty";
import { JOB_EDIT_FIELD_ORDER, validateJob } from "@/utils/validators";

import JobEditForm from "./JobEditForm";
import { FeaturedStarButton } from "./JobFormHelpers";


interface JobDialogProps {
  job: JobRead | null;
  companyName?: string;
  onClose: () => void;
  onSaved: (next: JobRead) => void;
  onError: () => void;
  onDelete: () => void;
  onApprove?: () => void;
  onReject?: () => void;
}

function seedFromJob(job: JobRead): JobAdminUpdate {
  return {
    title: job.title,
    short_description: job.short_description,
    description: job.description,
    requirements:
      job.requirements.length > 0
        ? job.requirements.map((r) => ({ text: r.text }))
        : Array.from({ length: JOB_REQ_MIN_COUNT }, () => ({ text: "" })),
    tags: [...job.tags],
    is_featured: job.is_featured,
    location: job.location,
    salary_min: job.salary_min ?? undefined,
    salary_max: job.salary_max ?? undefined,
    status: job.status,
  };
}

export default function JobDialog({
  job,
  companyName,
  onClose,
  onSaved,
  onError,
  onDelete,
  onApprove,
  onReject,
}: JobDialogProps) {
  const { t } = useTranslation(['admin', 'common']);

  const [form, setForm] = useState<JobAdminUpdate>({});
  const [initialForm, setInitialForm] = useState<JobAdminUpdate>({});
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Seed form whenever a new job session starts (new job opened, or job updated after save).
  useResetOnTrigger(job, () => {
    const seed = seedFromJob(job!);
    setForm(seed);
    setInitialForm(seed);
    setErrors({});
  });

  function set<K extends keyof JobAdminUpdate>(key: K, value: JobAdminUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: "" }));
  }

  function revert() {
    if (!job) return;
    const seed = seedFromJob(job);
    setForm(seed);
    setInitialForm(seed);
    setErrors({});
  }

  const isDirty = isDirtyByJSON(form, initialForm);

  const { handleClose, discardConfirm } = useConfirmableClose({ isDirty, onClose });

  function validate(): boolean {
    const e = validateJob(form, t);
    setErrors(e);
    if (Object.keys(e).length > 0) {
      focusFirstError(e, JOB_EDIT_FIELD_ORDER);
      return false;
    }
    return true;
  }

  async function save() {
    if (!job || !validate()) return;
    setSaving(true);
    try {
      const payload: JobAdminUpdate = {
        ...form,
        requirements: (form.requirements ?? [])
          .map((r) => ({ text: r.text.trim() }))
          .filter((r) => r.text.length > 0),
      };
      const updated = await updateJob(job.id, payload);
      // Immediately clear dirty state so the form reflects the saved values.
      const newSeed = seedFromJob(updated);
      setForm(newSeed);
      setInitialForm(newSeed);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  const isPending = job?.status === JobStatus.PENDING_APPROVAL;

  // Single wrapper div so Dialog's *:flex-1 gives it full width;
  // inside we split delete (left) from the rest (right).
  const footer = (
    <div className="flex w-full flex-wrap gap-2 sm:flex-nowrap sm:items-center">
      {isPending && onReject && (
        <Button variant="ghost" onClick={onReject} className="flex-1 sm:flex-none">
          {t("admin:jobs.reject")}
        </Button>
      )}
      {isPending && onApprove && (
        <Button variant="success" onClick={onApprove} className="flex-1 sm:flex-none">
          {t("admin:jobs.approve")}
        </Button>
      )}
      {isDirty && (
        <Button variant="ghost" onClick={revert} disabled={saving} className="flex-1 sm:flex-none">
          {t("common:revertChanges")}
        </Button>
      )}
      <Button
        variant="danger"
        onClick={() => setDeleteOpen(true)}
        className="flex-1 sm:order-first sm:me-auto sm:flex-none"
      >
        {t("admin:jobs.deleteAction")}
      </Button>
      <Button
        onClick={() => void save()}
        disabled={saving || !isDirty}
        className="w-full sm:w-auto"
      >
        {saving ? t("common:saving") : t("common:save")}
      </Button>
    </div>
  );

  if (!job) return null;
  return (
    <>
      <Dialog
        open={job != null}
        onOpenChange={(o) => !o && handleClose()}
        title={job.title}
        headerContent={
          <div className="pt-2 sm:pt-3">
            <div className="flex items-start gap-2">
              <AutoGrowTextarea
                id="title"
                value={form.title ?? ""}
                onChange={(v) => set("title", v.replace(/\n/g, ""))}
                minRows={1}
                placeholder={t("admin:jobs.placeholders.title")}
                className="w-full bg-transparent text-3xl font-semibold leading-snug text-white/90 placeholder:text-white/25 outline-none"
              />
              <FeaturedStarButton
                active={form.is_featured ?? false}
                onToggleRequest={() => set("is_featured", !(form.is_featured ?? false))}
              />
            </div>
            {errors.title && <p className="mt-1 text-xs text-danger">{errors.title}</p>}
            {(form.is_featured ?? false) !== job.is_featured && (
              <p className="mt-1 text-[11px] text-white/50">
                {(form.is_featured ?? false)
                  ? t("admin:jobs.featuredSetMessage")
                  : t("admin:jobs.featuredUnsetMessage")}
              </p>
            )}
          </div>
        }
        size="lg"
        preventOutsideClose
        footer={footer}
      >
        <div
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void save();
            }
          }}
        >
          <JobEditForm
            job={job}
            form={form}
            errors={errors}
            set={set}
            onStatusChange={(s) => set("status", s)}
            companyName={companyName}
          />
        </div>
      </Dialog>

      {discardConfirm}

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t("admin:jobs.deleteConfirmTitle")}
        message={t("admin:jobs.deleteConfirmMessage")}
        confirmLabel={t("admin:jobs.deleteConfirmYes")}
        variant="danger"
        onConfirm={() => { setDeleteOpen(false); onDelete(); }}
      />
    </>
  );
}

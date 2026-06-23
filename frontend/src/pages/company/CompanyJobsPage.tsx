import { type FormEvent, useCallback, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import {
  createJob,
  deleteJob,
  getCompanyJobs,
  updateJob,
} from "@/services/companyJobs";
import { errorAlertBaseCls, INPUT_CLS, TEXTAREA_CLS } from "@/styles/forms";
import { JobStatus } from "@/types/enums";
import type { JobCreate, JobRead, JobRequirementItem, JobUpdate } from "@/types/jobs";
import { JOB_SHORT_DESC_MAX, JOB_REQ_MIN_COUNT } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

const emptyRequirements = (): JobRequirementItem[] =>
  Array.from({ length: JOB_REQ_MIN_COUNT }, () => ({ text: "" }));

const EMPTY_FORM: JobCreate = {
  title: "",
  short_description: "",
  description: "",
  requirements: emptyRequirements(),
  tags: [],
  location: "",
  salary_min: 0,
  salary_max: 0,
};

interface JobFormProps {
  initial: JobCreate;
  onSubmit: (data: JobCreate) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
}

function JobForm({ initial, onSubmit, onCancel, submitLabel }: JobFormProps) {
  const { t } = useTranslation(["common", "company", "sm"]);
  const [form, setForm] = useState<JobCreate>(initial);
  const [isSaving, setIsSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function set<K extends keyof JobCreate>(field: K, val: JobCreate[K]) {
    setForm((prev) => ({ ...prev, [field]: val }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const filledReqs = form.requirements.filter((r) => r.text.trim().length > 0);
    if (filledReqs.length < JOB_REQ_MIN_COUNT) {
      setErr(t("common:validation.requirementsMin", { min: JOB_REQ_MIN_COUNT }));
      return;
    }
    setIsSaving(true);
    setErr(null);
    try {
      await onSubmit({
        ...form,
        requirements: filledReqs.map((r) => ({ text: r.text.trim() })),
      });
    } catch {
      setErr(t("company:jobs.errors.saveFailed"));
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.jobTitle")} <span className="text-copper/80">*</span>
          </label>
          <input
            type="text"
            required
            maxLength={200}
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
            className={`mt-1 ${INPUT_CLS}`}
            placeholder={t("company:jobs.placeholders.jobTitle")}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.location")} <span className="text-copper/80">*</span>
          </label>
          <input
            type="text"
            required
            maxLength={100}
            value={form.location}
            onChange={(e) => set("location", e.target.value)}
            className={`mt-1 ${INPUT_CLS}`}
            placeholder={t("company:jobs.placeholders.location")}
          />
        </div>
        <div>
          <label className="block text-sm text-white/50">
            {t("common:salaryMin")} (₪/חודש) <span className="text-copper/80">*</span>
          </label>
          <input
            type="number"
            required
            min={0}
            value={form.salary_min || ""}
            onChange={(e) =>
              set("salary_min", e.target.value ? Number(e.target.value) : 0)
            }
            className={`mt-1 ${INPUT_CLS}`}
          />
        </div>
        <div>
          <label className="block text-sm text-white/50">
            {t("common:salaryMax")} (₪/חודש) <span className="text-copper/80">*</span>
          </label>
          <input
            type="number"
            required
            min={0}
            value={form.salary_max || ""}
            onChange={(e) =>
              set("salary_max", e.target.value ? Number(e.target.value) : 0)
            }
            className={`mt-1 ${INPUT_CLS}`}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.shortDescription")}{" "}
            <span className="text-copper/80">*</span>
          </label>
          <input
            type="text"
            required
            maxLength={JOB_SHORT_DESC_MAX}
            value={form.short_description}
            onChange={(e) => set("short_description", e.target.value)}
            className={`mt-1 ${INPUT_CLS}`}
            placeholder={t("company:jobs.placeholders.shortDescription")}
          />
          <p className="mt-1 text-[11px] text-white/35">
            {t("common:charsRemaining", {
              count: JOB_SHORT_DESC_MAX - form.short_description.length,
            })}
          </p>
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.description")}{" "}
            <span className="text-copper/80">*</span>
          </label>
          <textarea
            required
            maxLength={5000}
            rows={4}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            className={`mt-1 ${TEXTAREA_CLS}`}
            placeholder={t("company:jobs.placeholders.description")}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.requirements")}{" "}
            <span className="text-copper/80">*</span>
          </label>
          <div className="mt-1">
            <JobRequirementsInput
              value={form.requirements}
              onChange={(reqs) => set("requirements", reqs)}
            />
          </div>
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.tags")}
          </label>
          <div className="mt-1">
            <JobTagsInput value={form.tags} onChange={(tags) => set("tags", tags)} />
          </div>
        </div>
      </div>

      {err && <p className="text-sm text-danger">{err}</p>}

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving}
          className="rounded-sm px-4 py-2 text-sm text-white/40 transition hover:bg-white/5 hover:text-white/70 disabled:opacity-40"
        >
          {t("company:jobs.cancel")}
        </button>
        <button
          type="submit"
          disabled={isSaving}
          className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white transition hover:bg-gold disabled:opacity-40"
        >
          {isSaving ? t("company:jobs.saving") : submitLabel}
        </button>
      </div>
    </form>
  );
}

type Mode = "idle" | "create" | { type: "edit"; job: JobRead };

export default function CompanyJobsPage() {
  const { t } = useTranslation(["common", "company", "sm"]);
  const [mode, setMode] = useState<Mode>("idle");
  const [deleting, setDeleting] = useState<number | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const fetcher = useCallback((cursor: string | null) => getCompanyJobs(cursor), []);
  const {
    items: jobs,
    isLoading: loading,
    isFetchingMore,
    hasMore,
    error: loadError,
    sentinelRef,
    prependItem,
    updateItem,
    removeItem,
  } = useInfiniteList<JobRead>(fetcher);

  const error = loadError ? t("company:jobs.errors.loadFailed") : mutationError;

  const STATUS_LABEL: Record<string, string> = {
    PENDING_APPROVAL: t("company:jobs.statusLabels.PENDING_APPROVAL"),
    PUBLISHED: t("company:jobs.statusLabels.PUBLISHED"),
    CLOSED: t("company:jobs.statusLabels.CLOSED"),
  };

  const STATUS_COLOR: Record<string, string> = {
    PENDING_APPROVAL: "bg-warning/10 text-warning",
    PUBLISHED: "bg-success/10 text-success",
    CLOSED: "bg-white/8 text-white/40",
  };

  async function handleCreate(data: JobCreate) {
    const job = await createJob(data);
    prependItem(job);
    setMode("idle");
  }

  async function handleEdit(jobId: number, data: JobCreate) {
    const update: JobUpdate = { ...data };
    const job = await updateJob(jobId, update);
    updateItem((j) => j.id === jobId, job);
    setMode("idle");
  }

  async function handleDelete(jobId: number) {
    if (!confirm(t("company:jobs.deleteConfirm"))) return;
    setDeleting(jobId);
    try {
      await deleteJob(jobId);
      removeItem((j) => j.id === jobId);
    } catch {
      setMutationError(t("company:jobs.errors.deleteFailed"));
    } finally {
      setDeleting(null);
    }
  }

  const isShowingForm =
    mode === "create" || (typeof mode === "object" && mode.type === "edit");

  return (
    <div>
      <PageHeader
        eyebrow={t("company:jobs.title")}
        subtitle={t("company:jobs.subtitle")}
        action={
          !isShowingForm ? (
            <Button onClick={() => setMode("create")}>
              {t("company:jobs.postJob")}
            </Button>
          ) : undefined
        }
      />

      {error && (
        <div className={`mb-4 ${errorAlertBaseCls} p-4`}>{error}</div>
      )}

      {isShowingForm && (
        <div className="mb-6 rounded-xl border border-copper/20 bg-card p-6">
          <Eyebrow className="mb-4">
            {mode === "create"
              ? t("company:jobs.createTitle")
              : t("company:jobs.editTitle")}
          </Eyebrow>
          <JobForm
            initial={
              typeof mode === "object" && mode.type === "edit"
                ? {
                    title: mode.job.title,
                    short_description: mode.job.short_description,
                    description: mode.job.description,
                    requirements:
                      mode.job.requirements.length > 0
                        ? mode.job.requirements.map((r) => ({ text: r.text }))
                        : emptyRequirements(),
                    tags: [...mode.job.tags],
                    location: mode.job.location,
                    salary_min: mode.job.salary_min ?? 0,
                    salary_max: mode.job.salary_max ?? 0,
                  }
                : EMPTY_FORM
            }
            onSubmit={
              typeof mode === "object" && mode.type === "edit"
                ? (data) => handleEdit(mode.job.id, data)
                : handleCreate
            }
            onCancel={() => setMode("idle")}
            submitLabel={
              mode === "create"
                ? t("company:jobs.submitForReview")
                : t("company:jobs.saveChanges")
            }
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16 text-white/25">
          {t("company:jobs.loading")}
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
          {t("company:jobs.empty")}
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const canEdit =
              job.status === JobStatus.PENDING_APPROVAL ||
              job.status === JobStatus.PUBLISHED;
            const canDelete = job.status === JobStatus.PENDING_APPROVAL;
            const isDeletingThisJob = deleting === job.id;

            return (
              <div
                key={job.id}
                className="flex flex-col gap-3 rounded-xl border border-white/8 bg-card p-5 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-white/85">{job.title}</p>
                    <StatusBadge
                      label={STATUS_LABEL[job.status]}
                      colorCls={STATUS_COLOR[job.status]}
                    />
                  </div>
                  <p className="mt-0.5 text-sm text-white/45">{job.location}</p>
                  <p className="mt-1 text-xs text-white/25">
                    {t("company:jobs.postedLabel")} {formatDate(job.created_at)}
                  </p>
                  <p className="mt-2 line-clamp-2 text-sm text-white/50">
                    {job.short_description || job.description}
                  </p>
                  {job.tags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {job.tags.slice(0, 4).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-copper/25 bg-copper/10 px-2 py-0.5 text-[11px] font-medium text-copper/90"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex shrink-0 gap-2">
                  {canEdit && (
                    <button
                      onClick={() => setMode({ type: "edit", job })}
                      disabled={isShowingForm}
                      className="rounded-sm border border-white/15 px-3 py-1.5 text-sm text-white/50 transition hover:border-white/30 hover:text-white/80 disabled:opacity-30"
                    >
                      {t("company:jobs.edit")}
                    </button>
                  )}
                  {canDelete && (
                    <button
                      onClick={() => handleDelete(job.id)}
                      disabled={isDeletingThisJob || isShowingForm}
                      className="rounded-sm border border-danger/20 px-3 py-1.5 text-sm text-danger transition hover:bg-danger/10 disabled:opacity-30"
                    >
                      {isDeletingThisJob ? "…" : t("company:jobs.delete")}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {(hasMore || isFetchingMore) && (
            <div ref={sentinelRef} className="py-4 text-center text-xs text-white/25">
              {isFetchingMore ? t("common:loading") : ""}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

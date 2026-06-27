import { type FormEvent, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import { INPUT_CLS, TEXTAREA_CLS } from "@/styles/forms";
import type { JobCreate } from "@/types/jobs";
import {
  JOB_DESC_MAX,
  JOB_REQ_MIN_COUNT,
  JOB_SHORT_DESC_MAX,
  JOB_TITLE_MAX,
} from "@/types/jobs";

const MIN_REQUIREMENTS = JOB_REQ_MIN_COUNT;

const TEXTAREA_ROWS = 4;

interface JobFormProps {
  initial: JobCreate;
  onSubmit: (data: JobCreate) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
}

export default function JobForm({ initial, onSubmit, onCancel, submitLabel }: JobFormProps) {
  const { t } = useTranslation(["common", "company"]);
  const [form, setForm] = useState<JobCreate>(initial);
  const [isSaving, setIsSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function set<K extends keyof JobCreate>(field: K, val: JobCreate[K]) {
    setForm((prev) => ({ ...prev, [field]: val }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const filledReqs = form.requirements.filter((r) => r.text.trim().length > 0);
    if (filledReqs.length < MIN_REQUIREMENTS) {
      setErr(t("common:validation.requirementsMin", { min: MIN_REQUIREMENTS }));
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
            maxLength={JOB_TITLE_MAX}
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
            onChange={(e) => set("salary_min", e.target.value ? Number(e.target.value) : 0)}
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
            onChange={(e) => set("salary_max", e.target.value ? Number(e.target.value) : 0)}
            className={`mt-1 ${INPUT_CLS}`}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.shortDescription")} <span className="text-copper/80">*</span>
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
            {t("common:charsRemaining", { count: JOB_SHORT_DESC_MAX - form.short_description.length })}
          </p>
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.description")} <span className="text-copper/80">*</span>
          </label>
          <textarea
            required
            maxLength={JOB_DESC_MAX}
            rows={TEXTAREA_ROWS}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            className={`mt-1 ${TEXTAREA_CLS}`}
            placeholder={t("company:jobs.placeholders.description")}
          />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm text-white/50">
            {t("company:jobs.form.requirements")} <span className="text-copper/80">*</span>
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
        <Button variant="ghost" type="button" onClick={onCancel} disabled={isSaving}>
          {t("company:jobs.cancel")}
        </Button>
        <Button type="submit" disabled={isSaving}>
          {isSaving ? t("company:jobs.saving") : submitLabel}
        </Button>
      </div>
    </form>
  );
}

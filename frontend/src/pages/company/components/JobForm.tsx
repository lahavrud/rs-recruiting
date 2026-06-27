import { type FormEvent, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import Field from "@/components/ui/Field";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import SalaryRangeField from "@/components/ui/SalaryRangeField";
import { INPUT_CLS, TEXTAREA_CLS, errorAlertCls } from "@/styles/forms";
import type { JobCreate } from "@/types/jobs";
import {
  JOB_DESC_MAX,
  JOB_LOCATION_MAX,
  JOB_REQ_MIN_COUNT,
  JOB_SHORT_DESC_MAX,
  JOB_TITLE_MAX,
} from "@/types/jobs";
const DESC_ROWS = 7;

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
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <section className="rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow className="mb-5">{t("company:jobs.form.sections.basics")}</Eyebrow>
        <div className="space-y-4">
          <Field id="jf-title" label={t("company:jobs.form.jobTitle")} required>
            <input
              id="jf-title"
              type="text"
              required
              maxLength={JOB_TITLE_MAX}
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              className={INPUT_CLS}
              placeholder={t("company:jobs.placeholders.jobTitle")}
            />
          </Field>

          <Field id="jf-location" label={t("company:jobs.form.location")} required>
            <input
              id="jf-location"
              type="text"
              required
              maxLength={JOB_LOCATION_MAX}
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              className={INPUT_CLS}
              placeholder={t("company:jobs.placeholders.location")}
            />
          </Field>
        </div>
      </section>

      <section className="rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow className="mb-5">{t("company:jobs.form.sections.description")}</Eyebrow>
        <div className="space-y-4">
          <Field
            id="jf-short"
            label={t("company:jobs.form.shortDescription")}
            required
            hint={t("common:charsRemaining", {
              count: JOB_SHORT_DESC_MAX - form.short_description.length,
            })}
          >
            <input
              id="jf-short"
              type="text"
              required
              maxLength={JOB_SHORT_DESC_MAX}
              value={form.short_description}
              onChange={(e) => set("short_description", e.target.value)}
              className={INPUT_CLS}
              placeholder={t("company:jobs.placeholders.shortDescription")}
            />
          </Field>

          <Field
            id="jf-desc"
            label={t("company:jobs.form.description")}
            required
            hint={t("common:charsRemaining", {
              count: JOB_DESC_MAX - form.description.length,
            })}
          >
            <textarea
              id="jf-desc"
              required
              maxLength={JOB_DESC_MAX}
              rows={DESC_ROWS}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              className={TEXTAREA_CLS}
              placeholder={t("company:jobs.placeholders.description")}
            />
          </Field>
        </div>
      </section>

      <section className="rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow className="mb-5">{t("company:jobs.form.sections.requirements")}</Eyebrow>
        <div className="space-y-2">
          <p className="flex items-center gap-1.5 text-xs text-white/55">
            {t("company:jobs.form.requirements")}
            <span className="text-copper/80">*</span>
          </p>
          <JobRequirementsInput
            value={form.requirements}
            onChange={(reqs) => set("requirements", reqs)}
          />
        </div>
      </section>

      <section className="rounded-xl border border-white/8 bg-card p-6">
        <Eyebrow className="mb-5">{t("company:jobs.form.sections.compensation")}</Eyebrow>
        <div className="space-y-6">
          <div>
            <p className="mb-1 text-xs text-white/55">{t("company:jobs.form.salaryRange")}</p>
            <SalaryRangeField
              min={form.salary_min}
              max={form.salary_max}
              onChange={(lo, hi) => {
                set("salary_min", lo);
                set("salary_max", hi);
              }}
            />
          </div>

          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-xs text-white/55">
              {t("company:jobs.form.tags")}
              <span className="text-[10px] text-white/30">({t("common:optional")})</span>
            </p>
            <JobTagsInput value={form.tags} onChange={(tags) => set("tags", tags)} />
          </div>
        </div>
      </section>

      {err && <div className={errorAlertCls}>{err}</div>}

      <div className="flex justify-end gap-2 pb-2">
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

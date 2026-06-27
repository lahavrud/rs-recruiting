import { type FormEvent, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import Field from "@/components/ui/Field";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import PageHeader from "@/components/ui/PageHeader";
import { EMPTY_FORM } from "@/pages/company/components/JobFormUtils";
import { createJob } from "@/services/companyJobs";
import { INPUT_CLS, TEXTAREA_CLS, errorAlertCls } from "@/styles/forms";
import type { JobCreate } from "@/types/jobs";
import {
  JOB_DESC_MAX,
  JOB_REQ_MIN_COUNT,
  JOB_SHORT_DESC_MAX,
  JOB_TITLE_MAX,
} from "@/types/jobs";

const LOCATION_MAX = 100;
const DESC_ROWS = 7;

export default function CompanyPostJobPage() {
  const { t } = useTranslation(["common", "company"]);
  const navigate = useNavigate();
  const [form, setForm] = useState<JobCreate>(EMPTY_FORM);
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
      const job = await createJob({
        ...form,
        requirements: filledReqs.map((r) => ({ text: r.text.trim() })),
      });
      navigate(`/company/jobs/${job.id}`);
    } catch {
      setErr(t("company:jobs.errors.saveFailed"));
      setIsSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader eyebrow={t("company:jobs.createTitle")} />

      <button
        type="button"
        onClick={() => navigate("/company/jobs")}
        className="mb-6 flex items-center gap-1.5 text-sm text-white/40 transition hover:text-white/70"
      >
        <span aria-hidden>→</span>
        {t("company:jobs.backToList")}
      </button>

      <div className="mb-6 rounded-lg border border-copper/20 bg-copper/5 px-4 py-3 text-sm text-copper/75">
        {t("company:jobs.postJobBanner")}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Basic info */}
        <section className="rounded-xl border border-white/8 bg-card p-6">
          <Eyebrow className="mb-5">{t("company:jobs.form.sections.basics")}</Eyebrow>
          <div className="space-y-4">
            <Field id="pj-title" label={t("company:jobs.form.jobTitle")} required>
              <input
                id="pj-title"
                type="text"
                required
                maxLength={JOB_TITLE_MAX}
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                className={INPUT_CLS}
                placeholder={t("company:jobs.placeholders.jobTitle")}
              />
            </Field>

            <Field id="pj-location" label={t("company:jobs.form.location")} required>
              <input
                id="pj-location"
                type="text"
                required
                maxLength={LOCATION_MAX}
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
                className={INPUT_CLS}
                placeholder={t("company:jobs.placeholders.location")}
              />
            </Field>
          </div>
        </section>

        {/* Description */}
        <section className="rounded-xl border border-white/8 bg-card p-6">
          <Eyebrow className="mb-5">{t("company:jobs.form.sections.description")}</Eyebrow>
          <div className="space-y-4">
            <Field
              id="pj-short"
              label={t("company:jobs.form.shortDescription")}
              required
              hint={t("common:charsRemaining", {
                count: JOB_SHORT_DESC_MAX - form.short_description.length,
              })}
            >
              <input
                id="pj-short"
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
              id="pj-desc"
              label={t("company:jobs.form.description")}
              required
              hint={t("common:charsRemaining", {
                count: JOB_DESC_MAX - form.description.length,
              })}
            >
              <textarea
                id="pj-desc"
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

        {/* Requirements */}
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

        {/* Compensation & tags */}
        <section className="rounded-xl border border-white/8 bg-card p-6">
          <Eyebrow className="mb-5">{t("company:jobs.form.sections.compensation")}</Eyebrow>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="pj-salary-min"
                label={`${t("common:salaryMin")} (₪/חודש)`}
                required
              >
                <input
                  id="pj-salary-min"
                  type="number"
                  required
                  min={0}
                  value={form.salary_min || ""}
                  onChange={(e) =>
                    set("salary_min", e.target.value ? Number(e.target.value) : 0)
                  }
                  className={INPUT_CLS}
                  dir="ltr"
                />
              </Field>
              <Field
                id="pj-salary-max"
                label={`${t("common:salaryMax")} (₪/חודש)`}
                required
              >
                <input
                  id="pj-salary-max"
                  type="number"
                  required
                  min={0}
                  value={form.salary_max || ""}
                  onChange={(e) =>
                    set("salary_max", e.target.value ? Number(e.target.value) : 0)
                  }
                  className={INPUT_CLS}
                  dir="ltr"
                />
              </Field>
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
          <Button
            variant="ghost"
            type="button"
            onClick={() => navigate("/company/jobs")}
            disabled={isSaving}
          >
            {t("company:jobs.cancel")}
          </Button>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? t("company:jobs.saving") : t("company:jobs.submitForReview")}
          </Button>
        </div>
      </form>
    </div>
  );
}

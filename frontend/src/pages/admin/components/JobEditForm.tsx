import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import AutoGrowTextarea from "@/components/ui/AutoGrowTextarea";
import Eyebrow from "@/components/ui/Eyebrow";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import { getApplications } from "@/services/adminApplications";
import { ghostInputCls } from "@/styles/forms";
import { JobStatus } from "@/types/enums";
import { JOB_SHORT_DESC_MAX } from "@/types/jobs";
import type { JobAdminUpdate, JobRead, JobRequirementItem } from "@/types/jobs";

import { SalaryRangeField, StatusPills } from "./JobFormHelpers";

const APP_FETCH_LIMIT = 100;

interface JobEditFormProps {
  job: JobRead;
  form: JobAdminUpdate;
  errors: Record<string, string>;
  set: <K extends keyof JobAdminUpdate>(key: K, value: JobAdminUpdate[K]) => void;
  onStatusChange: (status: JobStatus) => void;
  companyName?: string;
}

const subLabelCls =
  "mb-1 block text-[10px] font-medium uppercase tracking-wider text-white/35";

export default function JobEditForm({
  job,
  form,
  errors,
  set,
  onStatusChange,
  companyName,
}: JobEditFormProps) {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const currentStatus = (form.status ?? job.status) as JobStatus;

  const [appCount, setAppCount] = useState<{ n: number; isCapped: boolean } | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getApplications({ job_id: job.id, limit: APP_FETCH_LIMIT }, ctrl.signal)
      .then((page) =>
        setAppCount({
          n: page.items.length,
          isCapped: page.items.length === APP_FETCH_LIMIT,
        }),
      )
      .catch(() => {});
    return () => ctrl.abort();
  }, [job.id]);

  return (
    <div className="space-y-5 text-sm">
      {/* ── Job identity ────────────────────────────────────── */}
      <div className="space-y-2">
        {/* Context bar: company link + application count */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => navigate(`/admin/companies?detail=${job.company_id}`)}
            className="rounded border border-copper/30 bg-copper/8 px-2.5 py-1 text-copper/85 transition hover:border-copper/55 hover:bg-copper/15 hover:text-copper active:scale-[0.97] sm:rounded-none sm:border-0 sm:bg-transparent sm:px-0 sm:py-0 sm:hover:bg-transparent sm:hover:underline"
          >
            {companyName ?? t("admin:jobs.companyLabel", { id: job.company_id })}
          </button>
          {appCount !== null &&
            (appCount.n > 0 ? (
              <button
                type="button"
                onClick={() => navigate(`/admin/applications?job=${job.id}`)}
                className="rounded border border-white/12 bg-white/4 px-2.5 py-1 text-white/55 transition hover:border-copper/30 hover:bg-copper/8 hover:text-copper active:scale-[0.97] sm:rounded-none sm:border-0 sm:bg-transparent sm:px-0 sm:py-0 sm:text-white/40 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline"
              >
                {appCount.isCapped ? `${appCount.n}+` : appCount.n}{" "}
                {t("admin:jobs.candidatesLabel")}
              </button>
            ) : (
              <span className="px-2.5 py-1 text-white/30 sm:px-0 sm:py-0">
                0 {t("admin:jobs.candidatesLabel")}
              </span>
            ))}
        </div>

        {/* Location row — icon + label + ghost input */}
        <div className="-mx-1.5 flex items-center gap-1.5 rounded-md border border-transparent px-1.5 py-0.5 transition hover:border-white/10 hover:bg-white/3 focus-within:border-copper/30">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className="size-3.5 shrink-0 text-white/30"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="m7.539 14.841.003.003.002.002a.755.755 0 0 0 .912 0l.002-.002.003-.003.012-.009a5.57 5.57 0 0 0 .19-.153 15.588 15.588 0 0 0 2.046-2.082c1.101-1.362 2.291-3.342 2.291-5.597A5 5 0 0 0 3 8c0 2.255 1.19 4.235 2.292 5.597a15.591 15.591 0 0 0 2.046 2.082 8.916 8.916 0 0 0 .19.153l.012.01ZM8 8.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1Z"
              clipRule="evenodd"
            />
          </svg>
          <span className="shrink-0 text-xs text-white/30">
            {t("admin:jobs.fields.location")}
          </span>
          <input
            id="location"
            name="location"
            type="text"
            value={form.location ?? ""}
            onChange={(e) => set("location", e.target.value)}
            placeholder={t("admin:jobs.placeholders.location")}
            className="min-w-[4ch] flex-1 bg-transparent text-sm text-white/60 placeholder:text-white/20 outline-none [field-sizing:content] focus:text-white/80"
          />
        </div>
        {errors.location && <p className="text-xs text-danger">{errors.location}</p>}

        {/* Status pills */}
        <StatusPills
          value={currentStatus}
          onChange={(s) => {
            if (s !== currentStatus) onStatusChange(s);
          }}
        />

        {currentStatus === JobStatus.CLOSED && job.status !== JobStatus.CLOSED && (
          <div className="rounded-sm bg-warning/8 px-2.5 py-2 text-[11px] leading-relaxed">
            <p className="font-medium text-warning/85">
              {t("admin:jobs.notifyClosingWarning")}
            </p>
            <ul className="mt-1 space-y-0.5 text-warning/65">
              {(["board", "company", "applications"] as const).map((k) => (
                <li key={k} className="flex items-start gap-1.5">
                  <span
                    aria-hidden="true"
                    className="mt-[3px] size-1 shrink-0 rounded-full bg-warning/40"
                  />
                  {t(`admin:jobs.notifyClosingEffects.${k}`)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {job.status === JobStatus.PUBLISHED && (
          <p className="rounded-sm bg-info/5 px-2 py-1 text-[11px] leading-relaxed text-info/55">
            {t("admin:jobs.notifyPublishedHint")}
          </p>
        )}
      </div>

      <hr className="border-white/8" />

      {/* ── Compensation ────────────────────────────────────── */}
      <div>
        <Eyebrow as="label" htmlFor="salary_min" isDim className="mb-1.5 block">
          {t("admin:jobs.fields.salaryRange")}
        </Eyebrow>
        <SalaryRangeField
          min={form.salary_min}
          max={form.salary_max}
          onChange={(lo, hi) => {
            set("salary_min", lo);
            set("salary_max", hi);
          }}
          error={errors.salary_min ?? errors.salary_max}
        />
      </div>

      <hr className="border-white/8" />

      {/* ── Content ─────────────────────────────────────────── */}
      <div className="space-y-4">
        <Eyebrow isDim>{t("admin:jobs.formSections.content")}</Eyebrow>

        <div>
          <label className={subLabelCls} htmlFor="short_description">
            {t("admin:jobs.fields.shortDescription")}
          </label>
          <input
            id="short_description"
            name="short_description"
            type="text"
            maxLength={JOB_SHORT_DESC_MAX}
            value={form.short_description ?? ""}
            onChange={(e) => set("short_description", e.target.value)}
            placeholder={t("admin:jobs.placeholders.shortDescription")}
            className={ghostInputCls}
          />
          <p className="mt-1 text-[11px] text-white/35">
            <bdi>
              {(form.short_description ?? "").length} / {JOB_SHORT_DESC_MAX}
            </bdi>{" "}
            {t("admin:jobs.fields.shortDescriptionHint")}
          </p>
          {errors.short_description && (
            <p className="mt-1 text-xs text-danger">{errors.short_description}</p>
          )}
        </div>

        <hr className="border-white/8" />

        <div>
          <label className={subLabelCls} htmlFor="description">
            {t("admin:jobs.fields.description")}
          </label>
          <AutoGrowTextarea
            value={form.description ?? ""}
            onChange={(v) => set("description", v)}
            minRows={5}
            placeholder={t("admin:jobs.placeholders.description")}
            className={ghostInputCls}
          />
          {errors.description && (
            <p className="mt-1 text-xs text-danger">{errors.description}</p>
          )}
        </div>
      </div>

      <hr className="border-white/8" />

      {/* ── Lists ───────────────────────────────────────────── */}
      <div>
        <Eyebrow isDim className="mb-1.5 block">
          {t("admin:jobs.fields.requirements")}
        </Eyebrow>
        <JobRequirementsInput
          value={form.requirements ?? []}
          onChange={(reqs: JobRequirementItem[]) => set("requirements", reqs)}
          error={errors.requirements}
        />
      </div>

      <div>
        <Eyebrow isDim className="mb-1.5 block">
          {t("admin:jobs.fields.tags")}
        </Eyebrow>
        <JobTagsInput
          value={form.tags ?? []}
          onChange={(tags: string[]) => set("tags", tags)}
          error={errors.tags}
        />
      </div>
    </div>
  );
}

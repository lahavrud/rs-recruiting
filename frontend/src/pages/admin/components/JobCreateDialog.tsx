import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import AutoGrowTextarea from "@/components/ui/AutoGrowTextarea";
import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Eyebrow from "@/components/ui/Eyebrow";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import { getActiveCompanies } from "@/services/adminCompanies";
import { createJob } from "@/services/adminJobs";
import { ghostInputCls, selectCls } from "@/styles/forms";
import type {
  ActiveCompanyRead,
  JobAdminCreate,
  JobRead,
  JobRequirementItem,
} from "@/types/api";
import {
  JOB_REQ_MIN_COUNT,
  JOB_SHORT_DESC_MAX,
  JobStatus,
} from "@/types/api";
import { focusFirstError } from "@/utils/focusFirstError";
import { JOB_CREATE_FIELD_ORDER, validateJob } from "@/utils/validators";

import {
  FeaturedStarButton,
  SalaryRangeField,
  StatusPills,
} from "./JobFormHelpers";

const emptyRequirements = (): JobRequirementItem[] =>
  Array.from({ length: JOB_REQ_MIN_COUNT }, () => ({ text: "" }));

const subLabelCls =
  "mb-1 block text-[10px] font-medium uppercase tracking-wider text-white/35";

interface CreateProps {
  open: boolean;
  onClose: () => void;
  onCreated: (job: JobRead) => void;
  onError: () => void;
}

export default function JobCreateDialog({ open, onClose, onCreated, onError }: CreateProps) {
  const { t } = useTranslation(['admin', 'common']);
  const [companies, setCompanies] = useState<ActiveCompanyRead[] | null>(null);
  const [companiesError, setCompaniesError] = useState(false);
  const [form, setForm] = useState<Partial<JobAdminCreate>>({
    title: "",
    short_description: "",
    description: "",
    requirements: emptyRequirements(),
    tags: [],
    is_featured: false,
    location: "",
    status: JobStatus.PUBLISHED,
    salary_min: undefined,
    salary_max: undefined,
  });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useResetOnTrigger(open, () => {
    setCompanies(null);
    setCompaniesError(false);
    setErrors({});
    setForm({
      title: "",
      short_description: "",
      description: "",
      requirements: emptyRequirements(),
      tags: [],
      is_featured: false,
      location: "",
      status: JobStatus.PUBLISHED,
      salary_min: undefined,
      salary_max: undefined,
    });
  });

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    getActiveCompanies({ limit: 100 }, ctrl.signal)
      .then((page) => {
        setCompanies(page.items);
        if (page.items.length > 0) {
          setForm((prev) => ({ ...prev, company_id: page.items[0].company_profile.id }));
        }
      })
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setCompaniesError(true);
      });
    return () => ctrl.abort();
  }, [open]);

  function set<K extends keyof JobAdminCreate>(key: K, value: JobAdminCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[String(key)]) setErrors((prev) => ({ ...prev, [String(key)]: "" }));
  }

  function validate(): boolean {
    const e = validateJob(form, t);
    setErrors(e);
    if (Object.keys(e).length > 0) {
      focusFirstError(e, JOB_CREATE_FIELD_ORDER);
      return false;
    }
    return true;
  }

  async function save() {
    if (!form.company_id || !validate()) return;
    setSaving(true);
    try {
      const created = await createJob({
        company_id: form.company_id,
        title: form.title!,
        short_description: form.short_description!,
        description: form.description!,
        requirements: (form.requirements ?? [])
          .map((r) => ({ text: r.text.trim() }))
          .filter((r) => r.text.length > 0),
        tags: form.tags ?? [],
        is_featured: form.is_featured ?? false,
        location: form.location!,
        salary_min: form.salary_min!,
        salary_max: form.salary_max!,
        status: form.status,
      });
      onCreated(created);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  const footer = (
    <div className="flex w-full items-center gap-2">
      <span className="flex-1" aria-hidden="true" />
      <Button variant="ghost" onClick={onClose} disabled={saving}>
        {t("common:cancel")}
      </Button>
      <Button onClick={() => void save()} disabled={saving}>
        {saving ? t("common:saving") : t("common:save")}
      </Button>
    </div>
  );

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(o) => !o && onClose()}
        title={t("admin:jobs.newJobModalTitle")}
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
            {form.is_featured && (
              <p className="mt-1 text-[11px] text-white/50">
                {t("admin:jobs.featuredSetMessage")}
              </p>
            )}
          </div>
        }
        size="lg"
        preventOutsideClose
        footer={footer}
      >
        <div
          className="space-y-5 text-sm"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void save();
            }
          }}
        >
          {/* ── Job identity ────────────────────────────────────── */}
          <div className="space-y-2">
            {/* Company selector */}
            <div>
              <Eyebrow as="label" htmlFor="company_id" dim className="mb-1.5 block">
                {t("admin:jobs.fields.company")}
              </Eyebrow>
              {companiesError ? (
                <p className="text-xs text-danger">{t("admin:jobs.errors.companiesLoadFailed")}</p>
              ) : companies == null ? (
                <p className="text-xs text-white/35">{t("common:loading")}</p>
              ) : (
                <select
                  id="company_id"
                  value={form.company_id ?? ""}
                  onChange={(e) => set("company_id", Number(e.target.value))}
                  className={selectCls}
                >
                  {companies.map((row) => (
                    <option
                      key={row.company_profile.id}
                      value={row.company_profile.id}
                      className="bg-well"
                    >
                      {row.company_profile.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Location row — icon + label + ghost input */}
            <div className="-mx-1.5 flex items-center gap-1.5 rounded-md border border-transparent px-1.5 py-0.5 transition hover:border-white/10 hover:bg-white/3 focus-within:border-copper/30">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3.5 shrink-0 text-white/30" aria-hidden="true">
                <path fillRule="evenodd" d="m7.539 14.841.003.003.002.002a.755.755 0 0 0 .912 0l.002-.002.003-.003.012-.009a5.57 5.57 0 0 0 .19-.153 15.588 15.588 0 0 0 2.046-2.082c1.101-1.362 2.291-3.342 2.291-5.597A5 5 0 0 0 3 8c0 2.255 1.19 4.235 2.292 5.597a15.591 15.591 0 0 0 2.046 2.082 8.916 8.916 0 0 0 .19.153l.012.01ZM8 8.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1Z" clipRule="evenodd" />
              </svg>
              <span className="shrink-0 text-xs text-white/30">{t("admin:jobs.fields.location")}</span>
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

            {/* Status */}
            <StatusPills
              value={(form.status ?? JobStatus.PUBLISHED) as JobStatus}
              onChange={(s) => set("status", s)}
            />
          </div>

          <hr className="border-white/8" />

          {/* ── Compensation ────────────────────────────────────── */}
          <div>
            <Eyebrow as="label" htmlFor="salary_min" dim className="mb-1.5 block">
              {t("admin:jobs.fields.salaryRange")}
            </Eyebrow>
            <SalaryRangeField
              min={form.salary_min}
              max={form.salary_max}
              onChange={(lo, hi) => { set("salary_min", lo); set("salary_max", hi); }}
              error={errors.salary_min ?? errors.salary_max}
            />
          </div>

          <hr className="border-white/8" />

          {/* ── Content ─────────────────────────────────────────── */}
          <div className="space-y-10">
            <Eyebrow dim className="mb-1.5 block">{t("admin:jobs.formSections.content")}</Eyebrow>

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
                <bdi>{(form.short_description ?? "").length} / {JOB_SHORT_DESC_MAX}</bdi>
                {" "}{t("admin:jobs.fields.shortDescriptionHint")}
              </p>
              {errors.short_description && (
                <p className="mt-1 text-xs text-danger">{errors.short_description}</p>
              )}
            </div>

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
            <Eyebrow dim className="mb-1.5 block">{t("admin:jobs.fields.requirements")}</Eyebrow>
            <JobRequirementsInput
              value={form.requirements ?? []}
              onChange={(reqs: JobRequirementItem[]) => set("requirements", reqs)}
              error={errors.requirements}
            />
          </div>

          <div>
            <Eyebrow dim className="mb-1.5 block">{t("admin:jobs.fields.tags")}</Eyebrow>
            <JobTagsInput
              value={form.tags ?? []}
              onChange={(tags: string[]) => set("tags", tags)}
              error={errors.tags}
            />
          </div>
        </div>
      </Dialog>

    </>
  );
}

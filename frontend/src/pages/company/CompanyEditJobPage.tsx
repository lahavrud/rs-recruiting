import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import PageHeader from "@/components/ui/PageHeader";
import JobForm from "@/pages/company/components/JobForm";
import { emptyRequirements } from "@/pages/company/components/JobFormUtils";
import { getCompanyJob, updateJob } from "@/services/companyJobs";
import type { JobCreate, JobRead, JobUpdate } from "@/types/jobs";

export default function CompanyEditJobPage() {
  const { t } = useTranslation(["common", "company"]);
  const navigate = useNavigate();
  const { jobId: jobIdParam } = useParams<{ jobId: string }>();
  const jobId = Number(jobIdParam);

  const [job, setJob] = useState<JobRead | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (isNaN(jobId)) { navigate("/company/jobs"); return; }
    let cancelled = false;
    getCompanyJob(jobId)
      .then((j) => { if (!cancelled) setJob(j); })
      .catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; };
  }, [jobId, navigate]);

  async function handleSave(data: JobCreate) {
    const update: JobUpdate = { ...data };
    await updateJob(jobId, update);
    navigate(`/company/jobs/${jobId}`);
  }

  if (isNaN(jobId)) return null;

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader eyebrow={t("company:jobs.editTitle")} />
        <p className="mt-4 text-sm text-danger">{t("company:jobs.errors.loadFailed")}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader eyebrow={t("company:jobs.editTitle")} />
        <div className="mt-6 space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-white/5" />
          ))}
        </div>
      </div>
    );
  }

  const initial: JobCreate = {
    title: job.title,
    short_description: job.short_description,
    description: job.description,
    requirements:
      job.requirements.length > 0
        ? job.requirements.map((r) => ({ text: r.text }))
        : emptyRequirements(),
    tags: [...job.tags],
    location: job.location,
    salary_min: job.salary_min ?? 0,
    salary_max: job.salary_max ?? 0,
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader eyebrow={t("company:jobs.editTitle")} />

      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-white/40 transition hover:text-white/70"
      >
        <span aria-hidden>→</span>
        {t("company:jobs.back")}
      </button>

      <JobForm
        initial={initial}
        onSubmit={handleSave}
        onCancel={() => navigate(-1)}
        submitLabel={t("company:jobs.saveChanges")}
      />
    </div>
  );
}

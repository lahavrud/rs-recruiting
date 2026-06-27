import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import PageHeader from "@/components/ui/PageHeader";
import JobForm from "@/pages/company/components/JobForm";
import { EMPTY_FORM } from "@/pages/company/components/JobFormUtils";
import { createJob } from "@/services/companyJobs";
import type { JobCreate } from "@/types/jobs";

export default function CompanyPostJobPage() {
  const { t } = useTranslation(["common", "company"]);
  const navigate = useNavigate();

  async function handleCreate(data: JobCreate) {
    const job = await createJob(data);
    navigate(`/company/jobs/${job.id}`);
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

      <JobForm
        initial={EMPTY_FORM}
        onSubmit={handleCreate}
        onCancel={() => navigate("/company/jobs")}
        submitLabel={t("company:jobs.submitForReview")}
      />
    </div>
  );
}

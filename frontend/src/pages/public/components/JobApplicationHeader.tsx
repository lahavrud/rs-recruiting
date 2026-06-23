import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import type { JobPublicRead } from "@/types/jobs";

interface JobApplicationHeaderProps {
  job: JobPublicRead | null;
  jobId: number;
}

export default function JobApplicationHeader({
  job,
  jobId,
}: JobApplicationHeaderProps) {
  const { t } = useTranslation(["http", "publicJobs"]);

  return (
    <>
      <Link
        to={`/jobs/${jobId}`}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-white/35 transition hover:text-copper"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-4"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06L7.28 11.78a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
        {t("publicJobs:application.backToJob")}
      </Link>

      {/* Compact job header */}
      <div className="mb-8 flex items-start justify-between gap-4 rounded-xl border border-white/8 bg-card p-5 sm:p-6">
        <div className="min-w-0">
          <Eyebrow>{t("publicJobs:application.applyFor")}</Eyebrow>
          <h1 className="mt-1 truncate text-lg font-semibold text-white/90 sm:text-xl">
            {job?.title}
          </h1>
          {job?.location && (
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-white/40">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                className="size-3 shrink-0"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M8 1.5A4.5 4.5 0 0 0 3.5 6c0 2.625 3.375 7.5 4.5 7.5S12.5 8.625 12.5 6A4.5 4.5 0 0 0 8 1.5ZM8 7.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"
                  clipRule="evenodd"
                />
              </svg>
              {job.location}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

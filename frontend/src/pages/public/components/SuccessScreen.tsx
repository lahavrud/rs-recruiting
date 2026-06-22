import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { JobPublicRead } from "@/types/api";

interface SuccessScreenProps {
  job: JobPublicRead | null;
  claimAccount: boolean;
}

export default function SuccessScreen({ job, claimAccount }: SuccessScreenProps) {
  const { t } = useTranslation('publicJobs');

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-8">
      <div className="w-full max-w-2xl">
        <div className="rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("publicJobs:application.submitted")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("publicJobs:application.submittedMessage")}{" "}
            <span className="text-white/70">{job?.title}</span>.{" "}
            {t("publicJobs:application.submittedDetail")}
          </p>
          {claimAccount && (
            <p className="mt-4 rounded-lg border border-copper/20 bg-copper/5 px-4 py-3 text-sm leading-relaxed text-white/65">
              {t("publicJobs:application.claim.accountCreated")}
            </p>
          )}
          <Link
            to="/jobs"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("publicJobs:application.browseMore")}
          </Link>
        </div>
      </div>
    </div>
  );
}

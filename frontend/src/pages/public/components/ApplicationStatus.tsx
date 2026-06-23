import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { errorAlertClsLg } from "@/styles/forms";

interface ApplicationStatusProps {
  isLoading: boolean;
  error: string | null;
}

/**
 * Handles the two early-return states of the application page:
 * - Loading spinner while the job is being fetched
 * - Error state when the job cannot be loaded (404, network, etc.)
 *
 * Returns null when neither condition is active so the parent can render
 * the main form unaffected.
 */
export default function ApplicationStatus({ isLoading, error }: ApplicationStatusProps) {
  const { t } = useTranslation('publicJobs');

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="text-white/30">
          {t("publicJobs:application.loading")}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center">
        <div className={errorAlertClsLg}>
          {error}
        </div>
        <Link
          to="/jobs"
          className="mt-6 inline-block text-sm text-white/40 transition hover:text-copper"
        >
          {t("publicJobs:application.backToJob")}
        </Link>
      </div>
    );
  }

  return null;
}

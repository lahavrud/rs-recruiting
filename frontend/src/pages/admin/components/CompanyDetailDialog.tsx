import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Eyebrow from "@/components/ui/Eyebrow";
import { getJobs } from "@/services/adminJobs";
import type { CompanyProfileRead, JobRead } from "@/types/api";

interface DetailProps {
  profile: CompanyProfileRead | null;
  onClose: () => void;
  onEdit: () => void;
  /** Pending tab shows the same body but hides the Edit CTA. */
  hideEditButton?: boolean;
}

export default function CompanyDetailDialog({
  profile,
  onClose,
  onEdit,
  hideEditButton = false,
}: DetailProps) {
  const { t } = useTranslation(['admin', 'common']);
  const [jobs, setJobs] = useState<JobRead[] | null>(null);
  const [jobsError, setJobsError] = useState(false);

  useEffect(() => {
    if (!profile) return;
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setJobs(null);
    setJobsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    // No backend ?company_id= filter on /admin/jobs yet; fetch first page and
    // filter client-side. Adequate while companies have ~5 jobs each.
    getJobs({ limit: 100 }, ctrl.signal)
      .then((page) =>
        setJobs(page.items.filter((j) => j.company_id === profile.id)),
      )
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setJobsError(true);
      });
    return () => ctrl.abort();
  }, [profile]);

  if (!profile) return null;

  return (
    <Dialog
      open={profile != null}
      onOpenChange={(o) => !o && onClose()}
      title={profile.name}
      description={t("admin:companies.detailDescription")}
      size="lg"
      footer={
        hideEditButton ? undefined : (
          <Button
            onClick={onEdit}
          >
            {t("admin:companies.editAction")}
          </Button>
        )
      }
    >
      <CompanyDetailBody profile={profile} jobs={jobs} jobsError={jobsError} onLeavePage={onClose} />
    </Dialog>
  );
}

/**
 * Body content shared by the desktop CompanyDetailDialog and the mobile
 * inline expansion. Renders the profile fields + jobs section.
 */
export function CompanyDetailBody({
  profile,
  jobs: jobsProp,
  jobsError: jobsErrorProp,
  onLeavePage,
}: {
  profile: CompanyProfileRead;
  jobs?: JobRead[] | null;
  jobsError?: boolean;
  onLeavePage?: () => void;
}) {
  const { t } = useTranslation(['admin', 'common']);
  const navigate = useNavigate();
  const [localJobs, setLocalJobs] = useState<JobRead[] | null>(null);
  const [localJobsError, setLocalJobsError] = useState(false);
  // Self-fetch the jobs list when the parent didn't provide one (mobile inline).
  const useLocal = jobsProp === undefined;
  useEffect(() => {
    if (!useLocal) return;
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setLocalJobs(null);
    setLocalJobsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getJobs({ limit: 100 }, ctrl.signal)
      .then((page) =>
        setLocalJobs(page.items.filter((j) => j.company_id === profile.id)),
      )
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setLocalJobsError(true);
      });
    return () => ctrl.abort();
  }, [profile.id, useLocal]);
  const jobs = useLocal ? localJobs : jobsProp;
  const jobsError = useLocal ? localJobsError : (jobsErrorProp ?? false);
  return (
    <div className="space-y-4 text-sm">
      <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
        <dt className="text-white/35">{t("admin:companies.fields.companyId")}</dt>
        <dd className="text-white/70">
          {profile.company_id || t("admin:companies.noCompanyId")}
        </dd>
        {profile.contact_email && (
          <>
            <dt className="text-white/35">{t("admin:companies.fields.email")}</dt>
            <dd className="text-white/70">
              <a
                href={`mailto:${profile.contact_email}`}
                className="text-copper/85 transition hover:text-copper hover:underline"
              >
                {profile.contact_email}
              </a>
            </dd>
          </>
        )}
        {profile.address && (
          <>
            <dt className="text-white/35">{t("admin:companies.fields.address")}</dt>
            <dd className="text-white/70">{profile.address}</dd>
          </>
        )}
        {(profile.contact_first_name || profile.contact_last_name) && (
          <>
            <dt className="text-white/35">{t("admin:companies.contactLabel")}</dt>
            <dd className="text-white/70">
              {profile.contact_first_name} {profile.contact_last_name}
            </dd>
          </>
        )}
        {profile.contact_mobile_phone && (
          <>
            <dt className="text-white/35">
              {t("admin:companies.fields.contactMobile")}
            </dt>
            <dd className="text-white/70">{profile.contact_mobile_phone}</dd>
          </>
        )}
        {profile.contact_landline_phone && (
          <>
            <dt className="text-white/35">
              {t("admin:companies.fields.contactLandline")}
            </dt>
            <dd className="text-white/70">{profile.contact_landline_phone}</dd>
          </>
        )}
        {profile.user_id == null && (
          <>
            <dt className="text-white/35">—</dt>
            <dd className="text-white/40">{t("admin:companies.noUserAccount")}</dd>
          </>
        )}
      </dl>

      <div className="border-t border-white/8 pt-4">
        <Eyebrow>
          {t("admin:companies.jobsSection")}
        </Eyebrow>
        {jobsError ? (
          <p className="mt-3 text-xs text-danger">
            {t("admin:companies.errors.jobsLoadFailed")}
          </p>
        ) : jobs == null ? (
          <p className="mt-3 text-xs text-white/35">{t("common:loading")}</p>
        ) : jobs.length === 0 ? (
          <p className="mt-3 text-xs text-white/35">{t("admin:companies.noJobs")}</p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {jobs.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  onClick={() => {
                    onLeavePage?.();
                    navigate(`/admin/jobs?detail=${j.id}`);
                  }}
                  className="flex w-full items-center justify-between rounded-sm border border-white/6 bg-card px-3 py-2 transition hover:border-copper/25 hover:bg-card-raised"
                >
                  <span className="text-white/80">{j.title}</span>
                  <span className="text-xs text-white/40">{j.location}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

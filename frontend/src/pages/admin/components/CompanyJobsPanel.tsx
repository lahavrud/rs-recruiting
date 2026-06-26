import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import StatusBadge from "@/components/ui/StatusBadge";
import { JOB_STATUS_COLORS } from "@/constants/statusColors";
import { getJobs } from "@/services/adminJobs";
import { JobStatus } from "@/types/enums";
import type { JobRead } from "@/types/jobs";
import { formatDate } from "@/utils/formatDate";

import { IconArrowRight } from "./TriageIcons";

interface Props {
  companyId: number;
}

const STATUS_LABELS_KEYS: Record<JobStatus, string> = {
  [JobStatus.PENDING_APPROVAL]: "admin:jobs.statusLabels.PENDING_APPROVAL",
  [JobStatus.PUBLISHED]: "admin:jobs.statusLabels.PUBLISHED",
  [JobStatus.CLOSED]: "admin:jobs.statusLabels.CLOSED",
};

export default function CompanyJobsPanel({ companyId }: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobRead[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setJobs(null);
    setError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    const ctrl = new AbortController();
    getJobs({ company_id: companyId, limit: 100 }, ctrl.signal)
      .then((page) => setJobs(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setError(true);
      });
    return () => ctrl.abort();
  }, [companyId]);

  if (error) {
    return (
      <p className="py-6 text-center text-xs text-danger">
        {t("admin:companies.record.jobsTab.loadError")}
      </p>
    );
  }

  if (jobs == null) {
    return (
      <ul className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <li key={i} className="h-16 animate-pulse rounded-xl bg-white/5" />
        ))}
      </ul>
    );
  }

  if (jobs.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-white/35">
        {t("admin:companies.record.jobsTab.empty")}
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {jobs.map((job) => (
        <li
          key={job.id}
          onClick={() => navigate(`/admin/jobs/${job.id}`)}
          className="group relative cursor-pointer rounded-xl border border-white/8 bg-card-raised p-4 pe-10 transition hover:border-white/15 hover:bg-card active:scale-[0.99]"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-medium text-white/90">{job.title}</p>
              <p className="mt-0.5 text-xs text-white/35">{formatDate(job.created_at)}</p>
            </div>
            <StatusBadge
              label={t(STATUS_LABELS_KEYS[job.status as JobStatus])}
              colorCls={JOB_STATUS_COLORS[job.status]}
            />
          </div>
          <IconArrowRight className="absolute end-3 top-1/2 size-4 -translate-y-1/2 -scale-x-100 text-white/25 transition group-hover:text-copper" />
        </li>
      ))}
    </ul>
  );
}

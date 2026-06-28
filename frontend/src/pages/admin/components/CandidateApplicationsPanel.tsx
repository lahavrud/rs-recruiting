import { useEffect, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import StatusBadge from "@/components/ui/StatusBadge";
import { getApplications } from "@/services/adminApplications";
import { getActiveCompanies } from "@/services/adminCompanies";
import type { ApplicationWithDetails } from "@/types/candidates";
import { formatDate } from "@/utils/formatDate";

import { IconArrowRight } from "./TriageIcons";

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-copper/10 text-copper",
  APPROVED_BY_ADMIN: "bg-success/10 text-success",
  REJECTED: "bg-danger/10 text-danger",
  HIRED: "bg-hired/10 text-hired",
  JOB_CLOSED: "bg-white/8 text-white/45",
  WITHDRAWN: "bg-white/3 text-white/25",
};

interface Props {
  candidateId: number;
}

/** Applications & relations panel for the candidate record pane. */
export default function CandidateApplicationsPanel({ candidateId }: Props) {
  const { t } = useTranslation('admin');
  const navigate = useNavigate();
  const [applications, setApplications] = useState<ApplicationWithDetails[] | null>(null);
  const [error, setError] = useState(false);
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(new Map());

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setApplications(null);
    setError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    const ctrl = new AbortController();
    getApplications({ candidate_id: candidateId, limit: 100 }, ctrl.signal)
      .then((page) => setApplications(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setError(true);
      });
    return () => ctrl.abort();
  }, [candidateId]);

  useEffect(() => {
    const ctrl = new AbortController();
    getActiveCompanies({ limit: 100 }, ctrl.signal)
      .then((page) =>
        setCompanyNameById(
          new Map(page.items.map((row) => [row.company_profile.id, row.company_profile.name])),
        ),
      )
      .catch(() => {
        /* best-effort */
      });
    return () => ctrl.abort();
  }, []);

  const STATUS_LABELS: Record<string, string> = {
    NEW: t("admin:applications.statusLabels.NEW"),
    APPROVED_BY_ADMIN: t("admin:applications.statusLabels.APPROVED_BY_ADMIN"),
    REJECTED: t("admin:applications.statusLabels.REJECTED"),
    HIRED: t("admin:applications.statusLabels.HIRED"),
    JOB_CLOSED: t("admin:applications.statusLabels.JOB_CLOSED"),
    WITHDRAWN: t("admin:applications.statusLabels.WITHDRAWN"),
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>{t("admin:candidates.applicationsSection")}</Eyebrow>
        {applications && applications.length > 0 && (
          <span className="text-xs text-white/40">
            {t("admin:candidates.applicationsCount", { count: applications.length })}
          </span>
        )}
      </div>

      {error ? (
        <p className="mt-3 text-xs text-danger">
          {t("admin:candidates.errors.applicationsLoadFailed")}
        </p>
      ) : applications == null ? (
        <ul className="mt-3 space-y-3" aria-hidden>
          {[0, 1].map((i) => (
            <li key={i} className="animate-pulse rounded-xl border border-white/8 bg-card-raised p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="h-4 w-3/4 rounded bg-white/8" />
                  <div className="h-3 w-1/3 rounded bg-white/5" />
                </div>
                <div className="h-5 w-16 rounded-full bg-white/8" />
              </div>
            </li>
          ))}
        </ul>
      ) : applications.length === 0 ? (
        <p className="mt-3 text-xs text-white/35">{t("admin:candidates.noApplications")}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {applications.map((a) => (
            <li
              key={a.id}
              onClick={() => navigate(`/admin/applications/${a.id}`)}
              className="group relative cursor-pointer rounded-xl border border-white/8 bg-card-raised p-4 pe-10 transition hover:border-white/15 hover:bg-card active:scale-[0.99]"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-base font-medium text-white/90">{a.job.title}</p>
                  <p className="mt-1 text-xs text-white/40">{formatDate(a.created_at)}</p>
                  <p className="mt-0.5 text-[11px] text-white/30">
                    {companyNameById.get(a.job.company_id) ?? "—"}
                  </p>
                </div>
                <StatusBadge
                  label={STATUS_LABELS[a.status]}
                  colorCls={STATUS_COLORS[a.status]}
                />
              </div>

              <IconArrowRight
                className="absolute end-3 top-1/2 size-4 -translate-y-1/2 -scale-x-100 text-white/25 transition group-hover:text-copper"
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

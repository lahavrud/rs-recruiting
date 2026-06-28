import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import CompanyName from "@/components/ui/CompanyName";
import Eyebrow from "@/components/ui/Eyebrow";
import type { ApplicationWithDetails } from "@/types/candidates";

import { IconArrowRight } from "./TriageIcons";

interface Props {
  application: ApplicationWithDetails;
}

interface RelationRowProps {
  label: string;
  value: string | React.ReactNode;
  onClick: () => void;
}

function RelationRow({ label, value, onClick }: RelationRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center justify-between gap-3 rounded-lg border border-white/8 bg-card-raised px-4 py-3 text-start transition hover:border-white/15 hover:bg-card active:scale-[0.99]"
    >
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/35">
          {label}
        </p>
        <div className="mt-0.5 truncate text-sm font-medium text-white/85">{value}</div>
      </div>
      <IconArrowRight className="size-4 shrink-0 -scale-x-100 text-white/25 transition group-hover:text-copper" />
    </button>
  );
}

/** Links to all related entities: candidate, job, and company. */
export default function ApplicationRelationsPanel({ application: app }: Props) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();

  return (
    <div>
      <Eyebrow>{t("admin:applications.record.relationsSection")}</Eyebrow>
      <div className="mt-3 space-y-2">
        <RelationRow
          label={t("admin:applications.record.relationsCandidate")}
          value={app.candidate.full_name}
          onClick={() => navigate(`/admin/candidates/${app.candidate_id}`)}
        />
        <RelationRow
          label={t("admin:applications.record.relationsJob")}
          value={app.job.title}
          onClick={() => navigate(`/admin/jobs/${app.job_id}`)}
        />
        <RelationRow
          label={t("admin:applications.record.relationsCompany")}
          value={<CompanyName name={app.job.company_name} />}
          onClick={() => navigate(`/admin/companies/${app.job.company_id}`)}
        />
      </div>
    </div>
  );
}

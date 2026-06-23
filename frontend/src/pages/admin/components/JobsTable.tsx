import { useTranslation } from "react-i18next";

import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import StatusBadge from "@/components/ui/StatusBadge";
import type { JobRead } from "@/types/api";
import { JobStatus } from "@/types/api";
import { formatDate } from "@/utils/formatDate";

import { FeaturedDesktopSash } from "./JobViewBody";

export interface JobsTableProps {
  jobs: JobRead[];
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  onOpenDetail: (job: JobRead) => void;
  onEdit: (job: JobRead) => void;
  onApprove: (job: JobRead) => void;
  onReject: (job: JobRead) => void;
  onDelete: (job: JobRead) => void;
  onMailto: (job: JobRead) => void;
}

export default function JobsTable({
  jobs,
  statusLabels,
  statusColors,
  onOpenDetail,
  onEdit,
  onApprove,
  onReject,
  onDelete,
  onMailto,
}: JobsTableProps) {
  const { t } = useTranslation(['admin', 'common']);

  return (
    <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
      <table className="min-w-full divide-y divide-white/6 text-sm">
        <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
          <tr>
            <th className="px-4 py-3 text-start">
              {t("admin:jobs.fields.title")}
            </th>
            <th className="px-4 py-3 text-start">
              {t("admin:jobs.fields.location")}
            </th>
            <th className="px-4 py-3 text-start">
              {t("common:salary")}
            </th>
            <th className="px-4 py-3 text-start">
              {t("admin:jobs.fields.status")}
            </th>
            <th className="px-4 py-3 text-start">
              {t("admin:jobs.submittedLabel")}
            </th>
            <th className="px-4 py-3 text-end" aria-hidden />
          </tr>
        </thead>
        <tbody className="divide-y divide-white/6">
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => onOpenDetail(job)}
              className="cursor-pointer transition hover:bg-white/3"
            >
              <td className="relative px-4 py-3 font-medium text-white/85">
                {job.is_featured && <FeaturedDesktopSash />}
                <span>{job.title}</span>
              </td>
              <td className="px-4 py-3 text-white/60">{job.location}</td>
              <td className="px-4 py-3 text-sm text-copper/70">
                {job.salary_min != null && job.salary_max != null ? (
                  `${job.salary_min.toLocaleString("he-IL")}–${job.salary_max.toLocaleString("he-IL")} ₪`
                ) : (
                  <span className="text-white/20">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                <StatusBadge
                  label={statusLabels[job.status]}
                  colorCls={statusColors[job.status]}
                />
              </td>
              <td className="px-4 py-3 text-white/40">
                {formatDate(job.created_at)}
              </td>
              <td
                className="px-4 py-3 text-end"
                onClick={(e) => e.stopPropagation()}
              >
                <DropdownMenu
                  ariaLabel={t("admin:jobs.rowActionsLabel")}
                  trigger={<KebabButton size="sm" />}
                >
                  <DropdownMenuItem onSelect={() => onOpenDetail(job)}>
                    {t("admin:jobs.viewAction")}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onEdit(job)}>
                    {t("admin:jobs.editAction")}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onMailto(job)}>
                    {t("admin:jobs.email")}
                  </DropdownMenuItem>
                  {job.status === JobStatus.PENDING_APPROVAL && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onSelect={() => onApprove(job)}>
                        {t("admin:jobs.approve")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="danger"
                        onSelect={() => onReject(job)}
                      >
                        {t("admin:jobs.reject")}
                      </DropdownMenuItem>
                    </>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="danger"
                    onSelect={() => onDelete(job)}
                  >
                    {t("admin:jobs.deleteAction")}
                  </DropdownMenuItem>
                </DropdownMenu>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

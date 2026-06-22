import { useTranslation } from "react-i18next";

import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import type { JobRead } from "@/types/api";
import { JobStatus } from "@/types/api";

import { MobileJobCard } from "./JobViewBody";

export interface JobsListProps {
  jobs: JobRead[];
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  companyNameById: Map<number, string>;
  onEdit: (job: JobRead) => void;
  onApprove: (job: JobRead) => void;
  onReject: (job: JobRead) => void;
  onDelete: (job: JobRead) => void;
  onMailto: (job: JobRead) => void;
}

export default function JobsList({
  jobs,
  statusLabels,
  statusColors,
  companyNameById,
  onEdit,
  onApprove,
  onReject,
  onDelete,
  onMailto,
}: JobsListProps) {
  const { t } = useTranslation('admin');

  return (
    <div className="space-y-2 md:hidden">
      {jobs.map((job) => (
        <MobileJobCard
          key={job.id}
          job={job}
          statusLabels={statusLabels}
          statusColors={statusColors}
          companyName={companyNameById.get(job.company_id)}
          actions={
            <DropdownMenu
              ariaLabel={t("admin:jobs.rowActionsLabel")}
              trigger={
                <KebabButton onClick={(e) => e.stopPropagation()} />
              }
            >
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
          }
        />
      ))}
    </div>
  );
}

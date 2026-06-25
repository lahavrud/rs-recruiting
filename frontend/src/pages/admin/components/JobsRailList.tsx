import { useTranslation } from "react-i18next";

import RailRow from "@/components/admin/RailRow";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import StatusBadge from "@/components/ui/StatusBadge";
import { JOB_STATUS_COLORS } from "@/constants/statusColors";
import { useScrollSelectedIntoView } from "@/hooks/useScrollSelectedIntoView";
import { JobStatus } from "@/types/enums";
import type { JobRead } from "@/types/jobs";

interface JobsRailListProps {
  jobs: JobRead[];
  selectedId?: number | null;
  statusLabels: Record<string, string>;
  onView: (j: JobRead) => void;
  onEdit: (j: JobRead) => void;
  onApprove: (j: JobRead) => void;
  onReject: (j: JobRead) => void;
  onDelete: (j: JobRead) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

export default function JobsRailList({
  jobs,
  selectedId,
  statusLabels,
  onView,
  onEdit,
  onApprove,
  onReject,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: JobsRailListProps) {
  const { t } = useTranslation("admin");
  const rowRef = useScrollSelectedIntoView(selectedId, jobs);

  return (
    <>
      <div className="space-y-2">
        {jobs.map((j) => (
          <RailRow
            key={j.id}
            rowRef={rowRef(j.id)}
            selected={j.id === selectedId}
            onClick={() => onView(j)}
            actions={
              <DropdownMenu
                ariaLabel={t("admin:jobs.rowActionsLabel")}
                trigger={<KebabButton />}
              >
                <DropdownMenuItem onSelect={() => onView(j)}>
                  {t("admin:jobs.viewAction")}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onEdit(j)}>
                  {t("admin:jobs.editAction")}
                </DropdownMenuItem>
                {j.status === JobStatus.PENDING_APPROVAL && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={() => onApprove(j)}>
                      {t("admin:jobs.approve")}
                    </DropdownMenuItem>
                    <DropdownMenuItem variant="danger" onSelect={() => onReject(j)}>
                      {t("admin:jobs.reject")}
                    </DropdownMenuItem>
                  </>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="danger" onSelect={() => onDelete(j)}>
                  {t("admin:jobs.deleteAction")}
                </DropdownMenuItem>
              </DropdownMenu>
            }
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white/85">{j.title}</p>
              <div className="mt-0.5">
                <StatusBadge
                  label={statusLabels[j.status]}
                  colorCls={JOB_STATUS_COLORS[j.status]}
                />
              </div>
            </div>
          </RailRow>
        ))}
      </div>

      <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
    </>
  );
}

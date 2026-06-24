import { useTranslation } from "react-i18next";

import RailRow from "@/components/admin/RailRow";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import StatusBadge from "@/components/ui/StatusBadge";
import { useScrollSelectedIntoView } from "@/hooks/useScrollSelectedIntoView";
import type { ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

interface ApplicationsRailListProps {
  applications: ApplicationWithDetails[];
  selectedId?: number | null;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  onView: (app: ApplicationWithDetails) => void;
  onUpdateStatus: (app: ApplicationWithDetails) => void;
  onEditNotes: (app: ApplicationWithDetails) => void;
  onDelete: (app: ApplicationWithDetails) => void;
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingMore: boolean;
}

/** Compact rail list — a row per application, used for the 360px master list at every breakpoint. */
export default function ApplicationsRailList({
  applications,
  selectedId,
  statusLabels,
  statusColors,
  onView,
  onUpdateStatus,
  onEditNotes,
  onDelete,
  sentinelRef,
  isFetchingMore,
}: ApplicationsRailListProps) {
  const { t } = useTranslation("admin");
  const rowRef = useScrollSelectedIntoView(selectedId, applications);

  return (
    <>
      <div className="space-y-2">
        {applications.map((app) => (
          <RailRow
            key={app.id}
            rowRef={rowRef(app.id)}
            selected={app.id === selectedId}
            onClick={() => onView(app)}
            actions={
              <DropdownMenu
                ariaLabel={t("admin:applications.rowActionsLabel")}
                trigger={<KebabButton />}
              >
                <DropdownMenuItem onSelect={() => onView(app)}>
                  {t("admin:applications.viewAction")}
                </DropdownMenuItem>
                {app.status !== ApplicationStatus.WITHDRAWN && (
                  <DropdownMenuItem onSelect={() => onUpdateStatus(app)}>
                    {t("admin:applications.updateStatusAction")}
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onSelect={() => onEditNotes(app)}>
                  {t("admin:applications.editNotesAction")}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="danger" onSelect={() => onDelete(app)}>
                  {t("admin:applications.deleteAction")}
                </DropdownMenuItem>
              </DropdownMenu>
            }
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white/85">
                {app.candidate.full_name}
              </p>
              <p className="truncate text-xs text-white/40">{app.job.title}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <StatusBadge
                label={statusLabels[app.status]}
                colorCls={statusColors[app.status]}
              />
              <span className="text-[11px] text-white/40">
                {formatDate(app.created_at)}
              </span>
            </div>
          </RailRow>
        ))}
      </div>

      <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
    </>
  );
}

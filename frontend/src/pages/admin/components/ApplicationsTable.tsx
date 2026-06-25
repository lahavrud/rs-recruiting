import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import SortableColumnHeader from "@/components/admin/SortableColumnHeader";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import StatusBadge from "@/components/ui/StatusBadge";
import { APPLICATION_STATUS_COLORS } from "@/constants/statusColors";
import type { SortOrder } from "@/hooks/useColumnSort";
import { type ApplicationWithDetails } from "@/types/candidates";
import { ApplicationStatus } from "@/types/enums";
import { formatDate } from "@/utils/formatDate";

interface ColumnState {
  active: boolean;
  order: SortOrder;
  rank: 1 | 2 | undefined;
}

interface ApplicationsTableProps {
  applications: ApplicationWithDetails[];
  statusLabels: Record<string, string>;
  columnState: (column: "name" | "created_at" | "status") => ColumnState;
  onSort: (column: "name" | "created_at" | "status") => void;
  onUpdateStatus: (app: ApplicationWithDetails) => void;
  onEditNotes: (app: ApplicationWithDetails) => void;
  onDelete: (app: ApplicationWithDetails) => void;
}

export default function ApplicationsTable({
  applications,
  statusLabels,
  columnState,
  onSort,
  onUpdateStatus,
  onEditNotes,
  onDelete,
}: ApplicationsTableProps) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();

  const ariaSortAttr = (col: "name" | "created_at" | "status") => {
    const state = columnState(col);
    if (!state.active) return undefined;
    return state.order === "asc" ? ("ascending" as const) : ("descending" as const);
  };

  return (
    <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
      <table className="min-w-full divide-y divide-white/6 text-sm">
        <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
          <tr>
            <th className="px-4 py-3 text-start" aria-sort={ariaSortAttr("name")}>
              <SortableColumnHeader
                label={t("applications.table.candidate")}
                {...columnState("name")}
                onClick={() => onSort("name")}
              />
            </th>
            <th className="px-4 py-3 text-start">{t("applications.table.job")}</th>
            <th className="px-4 py-3 text-start" aria-sort={ariaSortAttr("status")}>
              <SortableColumnHeader
                label={t("applications.table.status")}
                {...columnState("status")}
                onClick={() => onSort("status")}
              />
            </th>
            <th className="px-4 py-3 text-start" aria-sort={ariaSortAttr("created_at")}>
              <SortableColumnHeader
                label={t("applications.table.date")}
                {...columnState("created_at")}
                onClick={() => onSort("created_at")}
              />
            </th>
            <th className="px-4 py-3 text-end" aria-hidden />
          </tr>
        </thead>
        <tbody className="divide-y divide-white/6">
          {applications.map((app) => (
            <tr
              key={app.id}
              onClick={() => navigate(`/admin/applications/${app.id}`)}
              className="cursor-pointer transition hover:bg-white/3"
            >
              <td className="px-4 py-3">
                <p className="font-medium text-white/85">{app.candidate.full_name}</p>
                <p className="text-xs text-white/40">{app.candidate.email}</p>
              </td>
              <td className="px-4 py-3">
                <p className="text-white/80">{app.job.title}</p>
                <p className="text-xs text-white/40">{app.job.location}</p>
              </td>
              <td className="px-4 py-3">
                <StatusBadge
                  label={statusLabels[app.status]}
                  colorCls={APPLICATION_STATUS_COLORS[app.status]}
                />
              </td>
              <td className="px-4 py-3 text-white/40">{formatDate(app.created_at)}</td>
              <td
                className="px-4 py-3 text-end"
                onClick={(e) => e.stopPropagation()}
              >
                <DropdownMenu
                  ariaLabel={t("applications.rowActionsLabel")}
                  trigger={<KebabButton size="sm" />}
                >
                  <DropdownMenuItem
                    onSelect={() => navigate(`/admin/applications/${app.id}`)}
                  >
                    {t("applications.viewAction")}
                  </DropdownMenuItem>
                  {app.status !== ApplicationStatus.WITHDRAWN && (
                    <DropdownMenuItem onSelect={() => onUpdateStatus(app)}>
                      {t("applications.updateStatusAction")}
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onSelect={() => onEditNotes(app)}>
                    {t("applications.editNotesAction")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="danger" onSelect={() => onDelete(app)}>
                    {t("applications.deleteAction")}
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

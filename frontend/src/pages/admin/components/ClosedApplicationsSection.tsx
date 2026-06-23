import { useState } from "react";

import { useTranslation } from "react-i18next";

import MobileEntityCard from "@/components/admin/MobileEntityCard";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import StatusBadge from "@/components/ui/StatusBadge";
import type { ApplicationWithDetails } from "@/types/candidates";
import { formatDate } from "@/utils/formatDate";

import { ApplicationDetailBody } from "./ApplicationDetailDialog";

interface Props {
  apps: ApplicationWithDetails[];
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  onView: (app: ApplicationWithDetails) => void;
  onUpdateStatus: (app: ApplicationWithDetails) => void;
  onEditNotes: (app: ApplicationWithDetails) => void;
  onDelete: (app: ApplicationWithDetails) => void;
}

export default function ClosedApplicationsSection({
  apps,
  statusLabels,
  statusColors,
  onView,
  onUpdateStatus,
  onEditNotes,
  onDelete,
}: Props) {
  const { t } = useTranslation("admin");
  const [isOpen, setIsOpen] = useState(false);

  if (apps.length === 0) return null;

  return (
    <div className="mt-6">
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-md border border-white/8 bg-card/40 px-4 py-3 text-sm text-white/50 transition hover:text-white/70"
      >
        <svg
          className={`size-4 shrink-0 transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="font-medium">{t("admin:applications.closedSection")}</span>
        <span className="ms-auto rounded-full bg-white/8 px-2 py-0.5 text-xs">
          {apps.length}
        </span>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`pt-2 transition-opacity duration-200 ${isOpen ? "opacity-100 delay-100" : "opacity-0"}`}
          >
            {/* Mobile */}
            <div className="space-y-2 md:hidden">
              {apps.map((app) => {
                const actions = (
                  <DropdownMenu
                    ariaLabel={t("admin:applications.rowActionsLabel")}
                    trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
                  >
                    <DropdownMenuItem onSelect={() => onUpdateStatus(app)}>
                      {t("admin:applications.updateStatusAction")}
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => onEditNotes(app)}>
                      {t("admin:applications.editNotesAction")}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem variant="danger" onSelect={() => onDelete(app)}>
                      {t("admin:applications.deleteAction")}
                    </DropdownMenuItem>
                  </DropdownMenu>
                );
                return (
                  <MobileEntityCard
                    key={app.id}
                    title={
                      <div className="min-w-0">
                        <p className="truncate font-medium text-white/85">
                          {app.candidate.full_name}
                        </p>
                        <p className="truncate text-[11px] font-normal text-white/50">
                          {app.job.title}
                        </p>
                      </div>
                    }
                    badge={
                      <StatusBadge
                        label={statusLabels[app.status]}
                        colorCls={statusColors[app.status]}
                      />
                    }
                    actions={actions}
                  >
                    <ApplicationDetailBody app={app} />
                  </MobileEntityCard>
                );
              })}
            </div>

            {/* Desktop */}
            <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
              <table className="min-w-full divide-y divide-white/6 text-sm">
                <tbody className="divide-y divide-white/6">
                  {apps.map((app) => (
                    <tr
                      key={app.id}
                      onClick={() => onView(app)}
                      className="cursor-pointer transition hover:bg-white/3"
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-white/60">
                          {app.candidate.full_name}
                        </p>
                        <p className="text-xs text-white/35">{app.candidate.email}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-white/55">{app.job.title}</p>
                        <p className="text-xs text-white/35">{app.job.location}</p>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          label={statusLabels[app.status]}
                          colorCls={statusColors[app.status]}
                        />
                      </td>
                      <td className="px-4 py-3 text-white/35">
                        {formatDate(app.created_at)}
                      </td>
                      <td
                        className="px-4 py-3 text-end"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <DropdownMenu
                          ariaLabel={t("admin:applications.rowActionsLabel")}
                          trigger={<KebabButton size="sm" />}
                        >
                          <DropdownMenuItem onSelect={() => onView(app)}>
                            {t("admin:applications.viewAction")}
                          </DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => onUpdateStatus(app)}>
                            {t("admin:applications.updateStatusAction")}
                          </DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => onEditNotes(app)}>
                            {t("admin:applications.editNotesAction")}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant="danger"
                            onSelect={() => onDelete(app)}
                          >
                            {t("admin:applications.deleteAction")}
                          </DropdownMenuItem>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useTranslation } from "react-i18next";

import MobileEntityCard from "@/components/admin/MobileEntityCard";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import type { CandidateProfileRead } from "@/types/api";
import { formatDate } from "@/utils/formatDate";

import { CandidateDetailBody } from "./CandidateDetailDialog";


interface CandidatesMobileListProps {
  candidates: CandidateProfileRead[];
  onEdit: (c: CandidateProfileRead) => void;
  onDelete: (c: CandidateProfileRead) => void;
}

export default function CandidatesMobileList({
  candidates,
  onEdit,
  onDelete,
}: CandidatesMobileListProps) {
  const { t } = useTranslation('admin');

  return (
    <div className="space-y-2 md:hidden">
      {candidates.map((c) => {
        const actions = (
          <DropdownMenu
            ariaLabel={t("admin:candidates.rowActionsLabel")}
            trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
          >
            <DropdownMenuItem onSelect={() => onEdit(c)}>
              {t("admin:candidates.editAction")}
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() =>
                window.open(
                  `mailto:${c.email}?subject=${encodeURIComponent(
                    t("admin:candidates.emailSubject", { name: c.full_name }),
                  )}`,
                  "_self",
                )
              }
            >
              {t("admin:candidates.emailAction")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="danger" onSelect={() => onDelete(c)}>
              {t("admin:candidates.deleteAction")}
            </DropdownMenuItem>
          </DropdownMenu>
        );
        return (
          <MobileEntityCard
            key={c.id}
            title={<span className="truncate text-white/85">{c.full_name}</span>}
            badge={
              <span className="text-[11px] text-white/40">{formatDate(c.created_at)}</span>
            }
            actions={actions}
          >
            <CandidateDetailBody candidate={c} />
          </MobileEntityCard>
        );
      })}
    </div>
  );
}

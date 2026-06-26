import { useCallback, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
import Button from "@/components/ui/Button";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useToast } from "@/hooks/useToast";
import { approveCompany, getPendingCompanies, rejectCompany } from "@/services/adminCompanies";
import type { PendingCompanyRead } from "@/types/companies";
import { formatDate } from "@/utils/formatDate";

import CompanyRecordPane from "./CompanyRecordPane";

function CompanyQueueItem({
  item,
  isSelected,
  onSelect,
  onApprove,
  onReject,
  isActing,
}: {
  item: PendingCompanyRead;
  isSelected: boolean;
  onSelect: () => void;
  onApprove: () => void;
  onReject: () => void;
  isActing: boolean;
}) {
  const { t } = useTranslation("admin");
  return (
    <div
      className={`flex items-start gap-2 rounded-lg border p-3 transition ${
        isSelected
          ? "border-copper/40 bg-copper/8"
          : "border-white/6 bg-card hover:border-white/12 hover:bg-card-raised"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="min-w-0 flex-1 text-start"
        aria-pressed={isSelected}
      >
        <p className="truncate font-medium text-white/90">
          {item.company_profile.name}
        </p>
        <p className="mt-0.5 truncate text-xs text-white/50">{item.user.email}</p>
        <p className="mt-0.5 text-xs text-white/30">
          {formatDate(item.company_profile.created_at)}
          {item.invitation_sent && (
            <span className="ms-2 text-white/25">
              · {t("admin:reviewQueue.inviteSent")}
            </span>
          )}
        </p>
      </button>
      <div className="flex shrink-0 flex-col gap-1">
        <Button
          variant="success"
          size="sm"
          onClick={onApprove}
          disabled={isActing}
        >
          {t("admin:reviewQueue.approved")}
        </Button>
        <Button
          variant="danger"
          size="sm"
          onClick={onReject}
          disabled={isActing}
        >
          {t("admin:reviewQueue.rejected")}
        </Button>
      </div>
    </div>
  );
}

export default function CompaniesQueue() {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<PendingCompanyRead>> =>
      getPendingCompanies({ cursor }),
    [],
  );

  const { items, isLoading, error, reload, sentinelRef, isFetchingMore, removeItem } =
    useInfiniteList<PendingCompanyRead>(fetcher);

  const selectedItem =
    selectedId != null
      ? items.find((c) => c.company_profile.id === selectedId)
      : undefined;

  function advance(profileId: number) {
    const idx = items.findIndex((c) => c.company_profile.id === profileId);
    const next = items[idx + 1] ?? items[idx - 1] ?? null;
    removeItem((c) => c.company_profile.id === profileId);
    setSelectedId(next?.company_profile.id ?? null);
  }

  async function handleApprove(profileId: number, userId: number) {
    setActingId(profileId);
    try {
      await approveCompany(userId);
      advance(profileId);
    } catch {
      toast.error(t("admin:reviewQueue.errors.approveFailed"));
    } finally {
      setActingId(null);
    }
  }

  async function handleReject(profileId: number, userId: number) {
    setActingId(profileId);
    try {
      await rejectCompany(userId);
      advance(profileId);
    } catch {
      toast.error(t("admin:reviewQueue.errors.rejectFailed"));
    } finally {
      setActingId(null);
    }
  }

  const rail = (
    <ListStateSwitch
      isLoading={isLoading}
      loading={<MobileListSkeleton rows={5} />}
      error={error}
      onRetry={reload}
      errorMessage={t("admin:companies.active.loadError")}
      isEmpty={items.length === 0}
      hasQuery={false}
      emptyEyebrow={t("admin:reviewQueue.tabs.companies")}
      emptyHeadline={t("admin:reviewQueue.empty.companies")}
    >
      <div className="space-y-1.5">
        {items.map((item) => (
          <CompanyQueueItem
            key={item.company_profile.id}
            item={item}
            isSelected={item.company_profile.id === selectedId}
            onSelect={() => setSelectedId(item.company_profile.id)}
            onApprove={() =>
              void handleApprove(item.company_profile.id, item.user.id)
            }
            onReject={() =>
              void handleReject(item.company_profile.id, item.user.id)
            }
            isActing={actingId === item.company_profile.id}
          />
        ))}
        <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
      </div>
    </ListStateSwitch>
  );

  return (
    <SplitPaneLayout
      collapsed={railCollapsed}
      onToggleCollapsed={() => setRailCollapsed((v) => !v)}
      showListLabel={t("admin:reviewQueue.record.showList")}
      hideListLabel={t("admin:reviewQueue.record.hideList")}
      rail={rail}
      record={
        <CompanyRecordPane
          companyId={selectedId}
          company={selectedItem?.company_profile}
          onEdit={(profile) => navigate(`/admin/companies/${profile.id}`)}
          onDelete={(profile) => navigate(`/admin/companies/${profile.id}`)}
        />
      }
    />
  );
}

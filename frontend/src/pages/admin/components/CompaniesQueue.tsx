import { useCallback, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import ListStateSwitch from "@/components/admin/ListStateSwitch";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SplitPaneLayout from "@/components/admin/SplitPaneLayout";
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
}: {
  item: PendingCompanyRead;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation("admin");
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border p-3 text-start transition ${
        isSelected
          ? "border-copper/40 bg-copper/8"
          : "border-white/6 bg-card hover:border-white/12 hover:bg-card-raised"
      }`}
      aria-pressed={isSelected}
    >
      <p className="truncate font-medium text-white/90">{item.company_profile.name}</p>
      <p className="mt-0.5 truncate text-xs text-white/50">{item.user.email}</p>
      <p className="mt-0.5 text-xs text-white/30">
        {formatDate(item.company_profile.created_at)}
        {item.invitation_sent && (
          <span className="ms-2 text-white/25">· {t("admin:reviewQueue.inviteSent")}</span>
        )}
      </p>
    </button>
  );
}

export default function CompaniesQueue() {
  const { t } = useTranslation(["admin", "common"]);
  const navigate = useNavigate();
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<number | null>(null);
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

  const queueList = (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
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
            />
          ))}
          <InfiniteScrollFooter sentinelRef={sentinelRef} isFetchingMore={isFetchingMore} />
        </div>
      </ListStateSwitch>
    </div>
  );

  const recordPane = (
    <CompanyRecordPane
      companyId={selectedId}
      company={selectedItem?.company_profile}
      onEdit={(profile) => navigate(`/admin/companies/${profile.id}`)}
      onDelete={(profile) => navigate(`/admin/companies/${profile.id}`)}
      onApprove={
        selectedItem != null
          ? () => void handleApprove(selectedItem.company_profile.id, selectedItem.user.id)
          : undefined
      }
      onReject={
        selectedItem != null
          ? () => void handleReject(selectedItem.company_profile.id, selectedItem.user.id)
          : undefined
      }
      isActing={actingId === selectedId}
    />
  );

  return (
    <>
      {selectedId == null ? (
        <div className="flex min-h-0 flex-1 flex-col md:hidden">{queueList}</div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col md:hidden">
          <button
            type="button"
            onClick={() => setSelectedId(null)}
            className="mb-3 text-start text-sm text-copper"
          >
            {t("admin:reviewQueue.record.showList")}
          </button>
          <div className="min-h-0 flex-1 overflow-y-auto">{recordPane}</div>
        </div>
      )}
      <div className="hidden min-h-0 flex-1 flex-col md:flex">
        <SplitPaneLayout
          recordPresent={selectedId != null}
          showListLabel={t("admin:reviewQueue.record.showList")}
          hideListLabel={t("admin:reviewQueue.record.hideList")}
          rail={queueList}
          record={recordPane}
        />
      </div>
    </>
  );
}

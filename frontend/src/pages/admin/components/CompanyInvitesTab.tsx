import { useCallback, useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";

import MobileEntityCard from "@/components/admin/MobileEntityCard";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";
import KebabButton from "@/components/ui/KebabButton";
import NoResults from "@/components/ui/NoResults";
import StatusBadge from "@/components/ui/StatusBadge";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useToast } from "@/hooks/useToast";
import {
  deleteInvite,
  getInvites,
  resendInvite,
  revokeInvite,
} from "@/services/adminInvites";
import { InviteTokenStatus } from "@/types/enums";
import type { InviteTokenRead } from "@/types/invites";
import { formatDate } from "@/utils/formatDate";

import InviteFormDialog from "./InviteFormDialog";

interface InvitesTabProps {
  query: string;
  isExternalOpen?: boolean;
  onExternalClose?: () => void;
}

export default function CompanyInvitesTab({
  query,
  isExternalOpen,
  onExternalClose,
}: InvitesTabProps) {
  const { t } = useTranslation(["admin", "md"]);
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<InviteTokenRead>> =>
      getInvites({ cursor }),
    [],
  );

  const {
    items: invites,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    prependItem,
    updateItem,
    removeItem,
  } = useInfiniteList<InviteTokenRead>(fetcher);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return invites;
    return invites.filter((i) => i.email.toLowerCase().includes(q));
  }, [invites, query]);

  const [isInviteFormOpen, setIsInviteFormOpen] = useState(false);
  const [revokePending, setRevokePending] = useState<InviteTokenRead | null>(null);
  const [deletePending, setDeletePending] = useState<InviteTokenRead | null>(null);
  const [isPendingMutation, setIsPendingMutation] = useState(false);
  const [resendingId, setResendingId] = useState<number | null>(null);

  useEffect(() => {
    if (isExternalOpen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsInviteFormOpen(true);
      onExternalClose?.();
    }
  }, [isExternalOpen, onExternalClose]);

  async function handleRevokeConfirm() {
    if (!revokePending) return;
    setIsPendingMutation(true);
    try {
      await revokeInvite(revokePending.id);
      updateItem((i) => i.id === revokePending.id, {
        ...revokePending,
        status: InviteTokenStatus.REVOKED,
      });
      toast.success(t("admin:companies.revokedToast"));
      setRevokePending(null);
    } catch {
      toast.error(t("admin:companies.inviteList.revokeError"));
    } finally {
      setIsPendingMutation(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setIsPendingMutation(true);
    try {
      await deleteInvite(deletePending.id);
      removeItem((i) => i.id === deletePending.id);
      toast.success(t("admin:companies.inviteDeletedToast"));
      setDeletePending(null);
    } catch {
      toast.error(t("admin:companies.inviteList.deleteError"));
    } finally {
      setIsPendingMutation(false);
    }
  }

  async function handleResend(invite: InviteTokenRead) {
    if (resendingId !== null) return;
    setResendingId(invite.id);
    const wasPending = invite.status === InviteTokenStatus.PENDING;
    try {
      await resendInvite(invite.id);
      // Resend regenerates the token + extends expiry; refresh the row so the
      // user sees the new expires_at and status flips back to PENDING if it
      // had drifted to EXPIRED or REVOKED.
      toast.success(
        wasPending
          ? t("admin:companies.resentToast")
          : t("admin:companies.reactivatedToast"),
      );
      reload();
    } catch {
      toast.error(t("admin:companies.inviteList.resendError"));
    } finally {
      setResendingId(null);
    }
  }

  function renderRowMenu(invite: InviteTokenRead) {
    const isPending = invite.status === InviteTokenStatus.PENDING;
    const isUsed = invite.status === InviteTokenStatus.USED;
    // Revoked/expired invites can be reactivated — `resend_invite` only
    // rejects USED, since once the user has registered, a fresh invite has
    // no meaning. The label flips to "הפעל מחדש" to convey activation rather
    // than re-sending the same link.
    const canResend = !isUsed;
    return (
      <DropdownMenu
        ariaLabel={t("admin:companies.rowActionsLabel")}
        trigger={<KebabButton onClick={(e) => e.stopPropagation()} />}
      >
        {canResend && (
          <DropdownMenuItem
            onSelect={() => handleResend(invite)}
            disabled={resendingId !== null}
          >
            {isPending
              ? t("admin:companies.resendAction")
              : t("admin:companies.reactivateAction")}
          </DropdownMenuItem>
        )}
        {isPending && (
          <DropdownMenuItem variant="danger" onSelect={() => setRevokePending(invite)}>
            {t("admin:companies.revokeAction")}
          </DropdownMenuItem>
        )}
        {(canResend || isPending) && <DropdownMenuSeparator />}
        <DropdownMenuItem variant="danger" onSelect={() => setDeletePending(invite)}>
          {t("admin:companies.deleteInviteAction")}
        </DropdownMenuItem>
      </DropdownMenu>
    );
  }

  return (
    <>
      {isLoading ? (
        <>
          <div className="md:hidden">
            <MobileListSkeleton rows={5} />
          </div>
          <div className="hidden md:block">
            <TableSkeleton rows={5} columns={4} />
          </div>
        </>
      ) : error ? (
        <ErrorState
          message={t("admin:companies.inviteList.loadError")}
          onRetry={reload}
        />
      ) : invites.length === 0 ? (
        <EmptyState
          eyebrow={t("admin:companies.tabs.invites")}
          headline={t("admin:companies.inviteList.empty")}
        />
      ) : filtered.length === 0 ? (
        <NoResults />
      ) : (
        <>
          {/* Mobile: collapsible card per invite */}
          <div className="space-y-2 md:hidden">
            {filtered.map((invite) => (
              <MobileEntityCard
                key={invite.id}
                title={
                  <span className="block truncate font-medium text-white/90">
                    {invite.email}
                  </span>
                }
                badge={<InviteStatusBadge status={invite.status} />}
                actions={renderRowMenu(invite)}
              >
                <InviteDetailBody invite={invite} />
              </MobileEntityCard>
            ))}
          </div>

          {/* Desktop: table */}
          <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th className="px-4 py-3 text-start">
                    {t("admin:companies.inviteList.columnEmail")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin:companies.inviteList.columnStatus")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin:companies.inviteList.columnCreated")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin:companies.inviteList.columnExpires")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {filtered.map((invite) => (
                  <tr key={invite.id}>
                    <td className="px-4 py-3 text-white/80">{invite.email}</td>
                    <td className="px-4 py-3">
                      <InviteStatusBadge status={invite.status} />
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(invite.created_at)}
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(invite.expires_at)}
                    </td>
                    <td className="px-4 py-3 text-end">{renderRowMenu(invite)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <InfiniteScrollFooter
            sentinelRef={sentinelRef}
            isFetchingMore={isFetchingMore}
          />
        </>
      )}

      <InviteFormDialog
        open={isInviteFormOpen}
        onClose={() => setIsInviteFormOpen(false)}
        onCreated={(invite) => {
          prependItem(invite);
          setIsInviteFormOpen(false);
        }}
      />

      <ConfirmDialog
        open={revokePending != null}
        onOpenChange={(o) => !o && setRevokePending(null)}
        title={t("admin:companies.revokeConfirmTitle")}
        message={t("admin:companies.inviteList.revokeConfirm")}
        confirmLabel={t("admin:companies.revokeAction")}
        variant="danger"
        isPending={isPendingMutation}
        onConfirm={handleRevokeConfirm}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin:companies.deleteInviteConfirmTitle")}
        message={t("admin:companies.inviteList.deleteConfirm")}
        confirmLabel={t("admin:companies.deleteInviteAction")}
        variant="danger"
        isPending={isPendingMutation}
        onConfirm={handleDeleteConfirm}
      />
    </>
  );
}

function InviteDetailBody({ invite }: { invite: InviteTokenRead }) {
  const { t } = useTranslation(["admin", "md"]);
  return (
    <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
      <dt className="text-white/35">{t("admin:companies.inviteList.columnStatus")}</dt>
      <dd>
        <InviteStatusBadge status={invite.status} />
      </dd>
      <dt className="text-white/35">{t("admin:companies.inviteList.columnCreated")}</dt>
      <dd className="text-white/70">{formatDate(invite.created_at)}</dd>
      <dt className="text-white/35">{t("admin:companies.inviteList.columnExpires")}</dt>
      <dd className="text-white/70">{formatDate(invite.expires_at)}</dd>
    </dl>
  );
}

function InviteStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation(["admin", "md"]);
  const cls =
    status === InviteTokenStatus.PENDING
      ? "bg-warning/10 text-warning"
      : status === InviteTokenStatus.USED
        ? "bg-success/10 text-success"
        : status === InviteTokenStatus.EXPIRED
          ? "bg-white/8 text-white/40"
          : "bg-danger/10 text-danger";
  return (
    <StatusBadge
      label={t(`admin:companies.inviteStatusLabels.${status}`)}
      colorCls={cls}
    />
  );
}

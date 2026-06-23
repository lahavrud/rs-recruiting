import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type { InviteTokenStatus } from "@/types/enums";
import type { InviteTokenCreate, InviteTokenRead } from "@/types/invites";
export interface InvitesListParams {
  cursor?: string | null;
  limit?: number;
  status?: InviteTokenStatus;
}

export async function createInvite(data: InviteTokenCreate): Promise<InviteTokenRead> {
  const res = await api.post<InviteTokenRead>("/api/admin/companies/invite", data);
  return res.data;
}

export async function getInvites(
  params?: InvitesListParams,
  signal?: AbortSignal,
): Promise<CursorPage<InviteTokenRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  if (params?.status) query.status = params.status;
  const res = await api.get<CursorPage<InviteTokenRead>>(
    "/api/admin/companies/invites",
    { params: query, signal },
  );
  return res.data;
}

export async function revokeInvite(tokenId: number): Promise<void> {
  await api.post(`/api/admin/companies/invites/${tokenId}/revoke`);
}

export async function deleteInvite(tokenId: number): Promise<void> {
  await api.delete(`/api/admin/companies/invites/${tokenId}`);
}

export async function resendInvite(tokenId: number): Promise<void> {
  await api.post(`/api/admin/companies/invites/${tokenId}/resend`);
}

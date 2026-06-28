import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type { AuditLogRead } from "@/types/audit";
import type { ApplicationRead, ApplicationStatusUpdate, ApplicationWithDetails } from "@/types/candidates";
import type { ApplicationStatus } from "@/types/enums";
export interface ApplicationListParams {
  status?: ApplicationStatus;
  job_id?: number;
  candidate_id?: number;
  q?: string;
  cursor?: string | null;
  limit?: number;
  sort?: "name" | "created_at" | "status" | "score";
  order?: "asc" | "desc";
  sort2?: "name" | "created_at" | "status";
  order2?: "asc" | "desc";
}

export async function getApplications(
  params?: ApplicationListParams,
  signal?: AbortSignal,
): Promise<CursorPage<ApplicationWithDetails>> {
  const query: Record<string, string | number> = {};
  if (params?.status) query.status = params.status;
  if (params?.job_id != null) query.job_id = params.job_id;
  if (params?.candidate_id != null) query.candidate_id = params.candidate_id;
  if (params?.q?.trim()) query.q = params.q.trim();
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  if (params?.sort) query.sort = params.sort;
  if (params?.order) query.order = params.order;
  if (params?.sort2) query.sort2 = params.sort2;
  if (params?.order2) query.order2 = params.order2;
  const res = await api.get<CursorPage<ApplicationWithDetails>>(
    "/api/admin/applications",
    { params: query, signal },
  );
  return res.data;
}

export async function getApplication(
  id: number,
  signal?: AbortSignal,
): Promise<ApplicationWithDetails> {
  const res = await api.get<ApplicationWithDetails>(`/api/admin/applications/${id}`, {
    signal,
  });
  return res.data;
}

export interface ApplicationActivityParams {
  cursor?: string | null;
  limit?: number;
}

export async function getApplicationActivity(
  id: number,
  params?: ApplicationActivityParams,
  signal?: AbortSignal,
): Promise<CursorPage<AuditLogRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<AuditLogRead>>(
    `/api/admin/applications/${id}/activity`,
    { params: query, signal },
  );
  return res.data;
}

export async function updateApplicationNotes(
  appId: number,
  adminNotes: string | null,
): Promise<ApplicationRead> {
  const res = await api.put<ApplicationRead>(`/api/admin/applications/${appId}/notes`, {
    admin_notes: adminNotes,
  });
  return res.data;
}

export async function updateApplicationStatus(
  appId: number,
  body: ApplicationStatusUpdate,
): Promise<ApplicationRead> {
  const res = await api.put<ApplicationRead>(
    `/api/admin/applications/${appId}/status`,
    body,
  );
  return res.data;
}

export async function deleteApplication(appId: number): Promise<void> {
  await api.delete(`/api/admin/applications/${appId}`);
}

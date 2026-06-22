import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type {
  ApplicationRead,
  ApplicationStatus,
  ApplicationStatusUpdate,
  ApplicationWithDetails,
} from "@/types/api";

export interface ApplicationListParams {
  status?: ApplicationStatus;
  job_id?: number;
  candidate_id?: number;
  cursor?: string | null;
  limit?: number;
}

export async function getApplications(
  params?: ApplicationListParams,
  signal?: AbortSignal,
): Promise<CursorPage<ApplicationWithDetails>> {
  const query: Record<string, string | number> = {};
  if (params?.status) query.status = params.status;
  if (params?.job_id != null) query.job_id = params.job_id;
  if (params?.candidate_id != null) query.candidate_id = params.candidate_id;
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<ApplicationWithDetails>>(
    "/api/admin/applications",
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

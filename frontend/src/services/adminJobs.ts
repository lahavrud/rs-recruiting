import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type { JobCandidateMatchRead } from "@/types/candidates";
import type { JobStatus } from "@/types/enums";
import type { JobAdminCreate, JobAdminUpdate, JobRead } from "@/types/jobs";
export interface JobListParams {
  status?: JobStatus;
  company_id?: number;
  q?: string;
  cursor?: string | null;
  limit?: number;
  sort?: "name" | "created_at" | "status";
  order?: "asc" | "desc";
  sort2?: "name" | "created_at" | "status";
  order2?: "asc" | "desc";
}

export async function approveJob(jobId: number): Promise<JobRead> {
  const res = await api.post<JobRead>(`/api/admin/jobs/${jobId}/approve`);
  return res.data;
}

export async function rejectJob(jobId: number): Promise<void> {
  await api.post(`/api/admin/jobs/${jobId}/reject`);
}

export async function contactJob(jobId: number, note: string): Promise<void> {
  await api.post(`/api/admin/jobs/${jobId}/contact`, { admin_note: note });
}

export async function getJobs(
  params?: JobListParams,
  signal?: AbortSignal,
): Promise<CursorPage<JobRead>> {
  const query: Record<string, string | number> = {};
  if (params?.status) query.status = params.status;
  if (params?.company_id != null) query.company_id = params.company_id;
  if (params?.q) query.q = params.q;
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  if (params?.sort) query.sort = params.sort;
  if (params?.order) query.order = params.order;
  if (params?.sort2) query.sort2 = params.sort2;
  if (params?.order2) query.order2 = params.order2;
  const res = await api.get<CursorPage<JobRead>>("/api/admin/jobs", {
    params: query,
    signal,
  });
  return res.data;
}

export async function getJob(id: number, signal?: AbortSignal): Promise<JobRead> {
  const res = await api.get<JobRead>(`/api/admin/jobs/${id}`, { signal });
  return res.data;
}

export async function createJob(body: JobAdminCreate): Promise<JobRead> {
  const res = await api.post<JobRead>("/api/admin/jobs", body);
  return res.data;
}

export async function updateJob(id: number, body: JobAdminUpdate): Promise<JobRead> {
  const res = await api.put<JobRead>(`/api/admin/jobs/${id}`, body);
  return res.data;
}

export async function deleteJob(id: number): Promise<void> {
  await api.delete(`/api/admin/jobs/${id}`);
}

export async function getJobCandidateMatches(
  jobId: number,
  signal?: AbortSignal,
): Promise<JobCandidateMatchRead[]> {
  const res = await api.get<JobCandidateMatchRead[]>(
    `/api/admin/jobs/${jobId}/candidate-matches`,
    { signal },
  );
  return res.data;
}

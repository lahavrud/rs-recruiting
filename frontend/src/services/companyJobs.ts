/**
 * Company job management API service.
 * All endpoints require COMPANY role JWT.
 */
import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type { JobCreate, JobRead, JobUpdate } from "@/types/api";

export async function getCompanyJobs(cursor: string | null = null): Promise<CursorPage<JobRead>> {
  const params: Record<string, string> = {};
  if (cursor) params.cursor = cursor;
  const res = await api.get<CursorPage<JobRead>>("/api/jobs/", { params });
  return res.data;
}

export async function createJob(data: JobCreate): Promise<JobRead> {
  const res = await api.post<JobRead>("/api/jobs/", data);
  return res.data;
}

export async function updateJob(jobId: number, data: JobUpdate): Promise<JobRead> {
  const res = await api.put<JobRead>(`/api/jobs/${jobId}`, data);
  return res.data;
}

export async function deleteJob(jobId: number): Promise<void> {
  await api.delete(`/api/jobs/${jobId}`);
}

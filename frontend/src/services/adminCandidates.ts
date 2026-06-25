import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type { CandidateActivityEvent } from "@/types/audit";
import type { CandidateJobMatchRead, CandidateProfileRead } from "@/types/candidates";

export interface CandidateListParams {
  cursor?: string | null;
  limit?: number;
}

export interface CandidateSearchParams extends CandidateListParams {
  q?: string;
  sort?: "name" | "created_at";
  order?: "asc" | "desc";
}

export async function getCandidates(
  params?: CandidateSearchParams,
  signal?: AbortSignal,
): Promise<CursorPage<CandidateProfileRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  if (params?.q) query.q = params.q;
  if (params?.sort) query.sort = params.sort;
  if (params?.order) query.order = params.order;
  const res = await api.get<CursorPage<CandidateProfileRead>>("/api/admin/candidates", {
    params: query,
    signal,
  });
  return res.data;
}

export async function getCandidate(
  id: number,
  signal?: AbortSignal,
): Promise<CandidateProfileRead> {
  const res = await api.get<CandidateProfileRead>(`/api/admin/candidates/${id}`, {
    signal,
  });
  return res.data;
}

export async function deleteCandidate(id: number): Promise<void> {
  await api.delete(`/api/admin/candidates/${id}`);
}

export async function getCandidateJobMatches(
  candidateId: number,
  signal?: AbortSignal,
): Promise<CandidateJobMatchRead[]> {
  const res = await api.get<CandidateJobMatchRead[]>(
    `/api/admin/candidates/${candidateId}/job-matches`,
    { signal },
  );
  return res.data;
}

export async function getCandidateActivity(
  id: number,
  params?: CandidateListParams,
  signal?: AbortSignal,
): Promise<CursorPage<CandidateActivityEvent>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<CandidateActivityEvent>>(
    `/api/admin/candidates/${id}/activity`,
    { params: query, signal },
  );
  return res.data;
}

// fetchResumeBlob is in this file because it's exclusively used in the
// candidates admin flow, even though the endpoint is not admin-namespaced.
export async function fetchResumeBlob(fileKey: string): Promise<Blob> {
  const res = await api.get<Blob>(`/api/resumes/${fileKey}`, {
    responseType: "blob",
  });
  return res.data;
}

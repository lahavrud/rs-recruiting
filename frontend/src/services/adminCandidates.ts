import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type { CandidateProfileRead, CandidateProfileUpdate } from "@/types/api";

export interface CandidateListParams {
  cursor?: string | null;
  limit?: number;
}

export async function getCandidates(
  params?: CandidateListParams,
  signal?: AbortSignal,
): Promise<CursorPage<CandidateProfileRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
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

export async function updateCandidate(
  id: number,
  body: CandidateProfileUpdate,
): Promise<CandidateProfileRead> {
  const res = await api.put<CandidateProfileRead>(`/api/admin/candidates/${id}`, body);
  return res.data;
}

export async function deleteCandidate(id: number): Promise<void> {
  await api.delete(`/api/admin/candidates/${id}`);
}

// fetchResumeBlob is in this file because it's exclusively used in the
// candidates admin flow, even though the endpoint is not admin-namespaced.
export async function fetchResumeBlob(fileKey: string): Promise<Blob> {
  const res = await api.get<Blob>(`/api/resumes/${fileKey}`, {
    responseType: "blob",
  });
  return res.data;
}

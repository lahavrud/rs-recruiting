import api from "@/services/api";
import type { ApplicationRead, ApplicationWithDetails } from "@/types/candidates";
import type { CandidateProfileRead } from "@/types/candidates";
import type { JobRead } from "@/types/jobs";

export interface GlobalMatchRead {
  candidate: CandidateProfileRead;
  job: JobRead;
  score: number;
}

export async function getGlobalMatches(
  limit = 20,
  signal?: AbortSignal,
): Promise<GlobalMatchRead[]> {
  const res = await api.get<GlobalMatchRead[]>("/api/admin/matches", {
    params: { limit },
    signal,
  });
  return res.data;
}

export async function getHotApplications(
  limit = 10,
  signal?: AbortSignal,
): Promise<ApplicationWithDetails[]> {
  const res = await api.get<ApplicationWithDetails[]>("/api/admin/matches/hot", {
    params: { limit },
    signal,
  });
  return res.data;
}

export async function pushMatch(
  candidateId: number,
  jobId: number,
  score: number,
): Promise<ApplicationRead> {
  const res = await api.post<ApplicationRead>("/api/admin/matches/push", {
    candidate_id: candidateId,
    job_id: jobId,
    score,
  });
  return res.data;
}

export async function dismissMatch(
  candidateId: number,
  jobId: number,
  score: number,
): Promise<void> {
  await api.post("/api/admin/matches/dismiss", {
    candidate_id: candidateId,
    job_id: jobId,
    score,
  });
}

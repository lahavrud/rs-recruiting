/**
 * Candidate self-service API client (Sprint 11 / #608).
 *
 * Wraps:
 *   GET    /api/candidate/me
 *   PATCH  /api/candidate/me
 *   POST   /api/candidate/me/resume          (multipart)
 *   DELETE /api/candidate/me/resume
 *   POST   /auth/me/password                  (role-agnostic in-session change)
 *   POST   /api/candidate/me/export           (async build → emailed link)
 */

import api from "@/services/api";

export interface CandidateMeRead {
  id: number;
  email: string;
  full_name: string;
  // Optional — only full_name + email are mandatory profile identity.
  // Phone / LinkedIn / resume are autofill metadata for the apply form
  // (Sprint 11 PR A). null after a deletion-PII-scrub too.
  phone: string | null;
  linkedin_url: string | null;
  resume_path: string | null;
  // Display label for resume_path — set on upload from the user's
  // original filename, editable later via PATCH (basename only;
  // extension is locked to the stored file's).
  resume_filename: string | null;
  consent_given_at: string | null;
  consent_policy_version: string | null;
  created_at: string;
}

export interface CandidateMeUpdate {
  full_name?: string;
  // Explicit null clears the column (the backend validator accepts it).
  phone?: string | null;
  linkedin_url?: string | null;
  resume_filename?: string | null;
}

export async function getMe(): Promise<CandidateMeRead> {
  const res = await api.get<CandidateMeRead>("/api/candidate/me");
  return res.data;
}

export async function patchMe(patch: CandidateMeUpdate): Promise<CandidateMeRead> {
  const res = await api.patch<CandidateMeRead>("/api/candidate/me", patch);
  return res.data;
}

export async function uploadResume(file: File): Promise<CandidateMeRead> {
  const data = new FormData();
  data.append("resume", file, file.name);
  const res = await api.post<CandidateMeRead>("/api/candidate/me/resume", data, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function deleteResume(): Promise<CandidateMeRead> {
  const res = await api.delete<CandidateMeRead>("/api/candidate/me/resume");
  return res.data;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await api.post("/auth/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function requestDataExport(): Promise<void> {
  await api.post("/api/candidate/me/export");
}

/* -------------------------------------------------------------------------
 * Session listing and revocation (#645)
 * ----------------------------------------------------------------------- */

export interface SessionRead {
  id: number;
  created_at: string;
  expires_at: string;
  user_agent: string | null;
  is_current: boolean;
}

export async function listSessions(): Promise<SessionRead[]> {
  const res = await api.get<SessionRead[]>("/api/auth/sessions");
  return res.data;
}

export async function revokeSession(sessionId: number): Promise<void> {
  await api.delete(`/api/auth/sessions/${sessionId}`);
}

export async function revokeAllSessions(): Promise<void> {
  await api.delete("/api/auth/sessions");
}

/* -------------------------------------------------------------------------
 * Application list + detail (Sprint 11 / #609)
 *
 * The candidate-facing API deliberately never surfaces raw application
 * status or admin notes — the only state signal is the `editable` flag,
 * reserved for a follow-up PR that adds edit/withdraw buttons.
 * ----------------------------------------------------------------------- */

export interface CandidateApplicationJobSummary {
  id: number;
  title: string;
  closed: boolean;
}

export interface CandidateApplicationJobDetail {
  id: number;
  title: string;
  description: string;
  closed: boolean;
}

export interface CandidateApplicationListItem {
  id: number;
  submitted_at: string;
  editable: boolean;
  job: CandidateApplicationJobSummary;
}

export interface CandidateApplicationMyAnswers {
  service_concept: string | null;
  salary_expectations: string | null;
  strength: string | null;
  growth_area: string | null;
}

export interface CandidateApplicationResumeMeta {
  filename: string;
  snapshot_present: boolean;
}

export interface CandidateApplicationDetail {
  id: number;
  submitted_at: string;
  editable: boolean;
  job: CandidateApplicationJobDetail;
  my_answers: CandidateApplicationMyAnswers;
  resume: CandidateApplicationResumeMeta | null;
}

export interface CandidateApplicationsPage {
  items: CandidateApplicationListItem[];
  next_cursor: string | null;
}

export async function listMyApplications(
  cursor?: string,
): Promise<CandidateApplicationsPage> {
  const res = await api.get<CandidateApplicationsPage>(
    "/api/candidate/me/applications",
    { params: cursor ? { cursor } : undefined },
  );
  return {
    items: res.data?.items ?? [],
    next_cursor: res.data?.next_cursor ?? null,
  };
}

export async function getMyApplication(
  applicationId: number,
): Promise<CandidateApplicationDetail> {
  const res = await api.get<CandidateApplicationDetail>(
    `/api/candidate/me/applications/${applicationId}`,
  );
  return res.data;
}

export async function fetchApplicationResumeBlob(applicationId: number): Promise<Blob> {
  const res = await api.get<Blob>(
    `/api/candidate/me/applications/${applicationId}/resume`,
    { responseType: "blob" },
  );
  return res.data;
}

export async function patchMyApplication(
  applicationId: number,
  form: FormData,
): Promise<CandidateApplicationDetail> {
  const res = await api.patch<CandidateApplicationDetail>(
    `/api/candidate/me/applications/${applicationId}`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return res.data;
}

export async function withdrawApplication(applicationId: number): Promise<void> {
  await api.post(`/api/candidate/me/applications/${applicationId}/withdraw`);
}

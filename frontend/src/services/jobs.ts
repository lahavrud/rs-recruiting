import type { CursorPage } from "@/hooks/useInfiniteList";
import api from "@/services/api";
import type {
  CandidateApplicationForm,
  CandidateProfileRead,
  JobPublicRead,
} from "@/types/api";

/** Fetch one page of published jobs for the public job board. */
export async function getPublicJobs(cursor: string | null = null): Promise<CursorPage<JobPublicRead>> {
  const params: Record<string, string> = {};
  if (cursor) params.cursor = cursor;
  const response = await api.get<CursorPage<JobPublicRead>>("/api/public/jobs", { params });
  return response.data;
}

/** Fetch a single published job by ID. Throws AxiosError 404 if not found. */
export async function getPublicJob(id: number): Promise<JobPublicRead> {
  const response = await api.get<JobPublicRead>(`/api/public/jobs/${id}`);
  return response.data;
}

/**
 * Submit a candidate application as multipart/form-data.
 * resume is optional — pass null if not provided.
 */
export async function submitApplication(
  jobId: number,
  form: Omit<CandidateApplicationForm, "job_id">,
  resume: File | null,
  options?: { password?: string | null },
): Promise<CandidateProfileRead> {
  const data = new FormData();

  // Append all text fields
  data.append("full_name", form.full_name);
  data.append("email", form.email);
  data.append("phone", form.phone);
  if (form.linkedin_url) data.append("linkedin_url", form.linkedin_url);
  if (form.service_concept) data.append("service_concept", form.service_concept);
  if (form.salary_expectations)
    data.append("salary_expectations", form.salary_expectations);
  if (form.growth_area) data.append("growth_area", form.growth_area);
  if (form.strength) data.append("strength", form.strength);

  // Legal consent — always true at this point (UI blocks submit otherwise).
  // The backend ignores these for logged-in candidates (consent already
  // captured at activation per Sprint 11 / #605).
  data.append("privacy_accepted", "true");
  data.append("terms_accepted", "true");

  // Optional claim-by-password (Sprint 11 / #606). When supplied alongside
  // an anonymous apply, the backend creates a pending candidate User +
  // activation token in the same transaction.
  if (options?.password) {
    data.append("password", options.password);
    data.append("password_confirm", options.password);
  }

  // Append resume file if provided
  if (resume) {
    data.append("resume", resume, resume.name);
  }

  // Explicit multipart Content-Type — the api instance defaults to
  // application/json, which would cause axios to JSON-stringify the
  // FormData and the backend's Form(...) parsers to see no fields.
  const response = await api.post<CandidateProfileRead>(
    `/api/jobs/${jobId}/apply`,
    data,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return response.data;
}

import type { ApplicationStatus } from "@/types/enums";
import type { components } from "@/types/generated";

type Schemas = components["schemas"];

// Response/read DTOs aliased to the generated OpenAPI types (regenerated + diffed
// in CI). Request bodies + client-only form shapes stay hand-written below.
export type CandidateProfileRead = Schemas["CandidateProfileRead"];
export type ApplicationRead = Schemas["ApplicationRead"];
export type ApplicationWithDetails = Schemas["ApplicationWithDetails"];
/** One ranked candidate match for the admin job view. score is cosine similarity in [0, 1]. */
export type JobCandidateMatchRead = Schemas["JobCandidateMatchRead"];
/** One ranked job match for the admin candidate view. score is cosine similarity in [0, 1]. */
export type CandidateJobMatchRead = Schemas["CandidateJobMatchRead"];

export interface ApplicationStatusUpdate {
  status: ApplicationStatus;
  admin_notes?: string | null;
}

/** Mirrors backend CandidateAdminRead — richer admin view with account + tombstone fields. */
export interface CandidateAdminRead {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
  resume_path: string | null;
  resume_summary: string | null;
  linkedin_url: string | null;
  created_at: string;
  deleted_at: string | null;
  ai_score: number | null;
  has_account: boolean;
  is_deleted: boolean;
  user_email: string | null;
  user_is_active: boolean | null;
}

/**
 * Form input shape for the application form — client-only. Submitted as
 * multipart/form-data to POST /api/candidates/apply (the file is handled
 * separately as File | null), so it has no standalone backend schema.
 */
export interface CandidateApplicationForm {
  job_id: number;
  full_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  // Interview questions
  service_concept: string;
  salary_expectations: string;
  growth_area: string;
  strength: string;
}

import type { ApplicationStatus } from "@/types/enums";
import type { JobRead } from "@/types/jobs";

/** Mirrors backend CandidateProfileRead schema. */
export interface CandidateProfileRead {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  resume_path: string | null;
  linkedin_url: string | null;
  created_at: string;
}

/**
 * Form input shape for the application form.
 * Submitted as multipart/form-data to POST /api/candidates/apply.
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
  // File — handled separately as File | null
}

export interface ApplicationRead {
  id: number;
  job_id: number;
  candidate_id: number;
  status: ApplicationStatus;
  admin_notes: string | null;
  service_concept: string | null;
  salary_expectations: string | null;
  strength: string | null;
  growth_area: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationWithDetails {
  id: number;
  job_id: number;
  candidate_id: number;
  status: ApplicationStatus;
  admin_notes: string | null;
  service_concept: string | null;
  salary_expectations: string | null;
  strength: string | null;
  growth_area: string | null;
  created_at: string;
  updated_at: string;
  job: JobRead;
  candidate: CandidateProfileRead;
}

export interface ApplicationStatusUpdate {
  status: ApplicationStatus;
  admin_notes?: string | null;
}

/** One ranked candidate match for the admin job view. score is cosine similarity in [0, 1]. */
export interface JobCandidateMatchRead {
  candidate: CandidateProfileRead;
  score: number;
}

/** One ranked job match for the admin candidate view. score is cosine similarity in [0, 1]. */
export interface CandidateJobMatchRead {
  job: JobRead;
  score: number;
}

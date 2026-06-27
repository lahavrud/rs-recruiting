import type { CompanyProfileRead, UserRead } from "@/types/auth";

export type { CompanyProfileRead };

export interface CompanyProfileSelfUpdate {
  name?: string;
  address?: string;
  contact_first_name?: string;
  contact_last_name?: string;
  contact_mobile_phone?: string;
  contact_landline_phone?: string | null;
}

export interface CompanyStats {
  active_jobs: number;
  pending_jobs: number;
  closed_jobs: number;
  total_applications: number;
  applications_by_status: Record<string, number>;
}

export interface CompanyApplicationCandidateRead {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
}

export interface CompanyApplicationRead {
  id: number;
  job_id: number;
  candidate_id: number;
  status: string;
  created_at: string;
  updated_at: string;
  match_score: number | null;
  ai_review: string | null;
  candidate: CompanyApplicationCandidateRead;
}

export interface CompanyJobRecommendationRead {
  candidate_id: number;
  full_name: string;
  email: string;
  phone: string | null;
  score: number;
}

export interface PendingCompanyRead {
  user: UserRead;
  company_profile: CompanyProfileRead;
  invitation_sent: boolean;
}

export interface ApprovedCompanyRead {
  user: UserRead;
  company_profile: CompanyProfileRead;
}

export interface ActiveCompanyRead {
  /** Null for profiles created directly by admins (no user account yet). */
  user: UserRead | null;
  company_profile: CompanyProfileRead;
}

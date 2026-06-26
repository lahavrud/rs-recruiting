import type { JobStatus } from "@/types/enums";

export const JOB_TITLE_MAX = 100;
export const JOB_LOCATION_MAX = 200;
export const JOB_DESC_MAX = 5000;
export const JOB_SHORT_DESC_MAX = 140;
export const JOB_TAG_MAX_LEN = 30;
export const JOB_TAG_MAX_COUNT = 6;
export const JOB_REQ_TEXT_MAX = 200;
export const JOB_REQ_MIN_COUNT = 3;
export const JOB_REQ_MAX_COUNT = 15;

/** Fallback salary bounds used when job list is empty or all salaries are equal. */
export const SALARY_FALLBACK = { min: 0, max: 50_000 } as const;

export interface JobRequirementItem {
  text: string;
}

export interface JobRead {
  id: number;
  company_id: number;
  company_name: string;
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  is_featured: boolean;
  location: string;
  salary_min: number;
  salary_max: number;
  status: JobStatus;
  created_at: string;
  updated_at: string;
}

export interface JobCreate {
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  location: string;
  salary_min: number;
  salary_max: number;
}

export interface JobUpdate {
  title?: string;
  short_description?: string;
  description?: string;
  requirements?: JobRequirementItem[];
  tags?: string[];
  location?: string;
  /** NOT NULL in DB — backend rejects explicit null. Omit to leave unchanged. */
  salary_min?: number;
  /** NOT NULL in DB — backend rejects explicit null. Omit to leave unchanged. */
  salary_max?: number;
  status?: JobStatus;
}

/** Mirrors backend JobAdminCreate schema. */
export interface JobAdminCreate {
  company_id: number;
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  is_featured?: boolean;
  location: string;
  salary_min: number;
  salary_max: number;
  status?: JobStatus;
}

/** Mirrors backend JobAdminUpdate — extends JobUpdate with is_featured. */
export interface JobAdminUpdate extends JobUpdate {
  is_featured?: boolean;
}

/** Candidate-side info about their own application for the job (Sprint 11 / #606). */
export interface MyApplicationInfo {
  id: number;
  /** True only when the application is still in NEW status — the candidate
   *  can edit / withdraw it. False means admin engaged with it. The raw
   *  status is intentionally hidden from candidate-facing payloads. */
  editable: boolean;
}

/** Mirrors backend JobPublicRead schema. Status is omitted (only PUBLISHED returned).
 *  `my_application` is populated only on the per-job detail endpoint when
 *  the request bears a candidate JWT; otherwise null. */
export interface JobPublicRead {
  id: number;
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  is_featured: boolean;
  location: string;
  salary_min: number;
  salary_max: number;
  created_at: string;
  my_application: MyApplicationInfo | null;
}

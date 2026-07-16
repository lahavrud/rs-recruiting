import type { JobStatus } from "@/types/enums";
import type { components } from "@/types/generated";

type Schemas = components["schemas"];

// Validation limits. These are runtime values (used by form validation), so they
// can't come from the generated types — openapi-typescript emits types only. They
// are kept in sync with the backend `maxLength`s in the spec by the parity test in
// `__tests__/contract.parity.test.ts`, which fails CI if either side drifts.
export const JOB_TITLE_MAX = 100;
export const JOB_LOCATION_MAX = 100;
export const JOB_DESC_MAX = 5000;
export const JOB_SHORT_DESC_MAX = 140;
export const JOB_TAG_MAX_LEN = 30;
export const JOB_TAG_MAX_COUNT = 6;
export const JOB_REQ_TEXT_MAX = 200;
export const JOB_REQ_MIN_COUNT = 3;
export const JOB_REQ_MAX_COUNT = 15;

/** Fallback salary bounds used when job list is empty or all salaries are equal. */
export const SALARY_FALLBACK = { min: 0, max: 50_000 } as const;

// Response DTOs are aliased directly to the generated OpenAPI types — they are exact
// mirrors of the backend schemas, so hand-maintaining them only invited drift. The
// generated `src/types/generated.ts` is regenerated + diffed in CI.
export type JobRequirementItem = Schemas["JobRequirementItem"];
export type JobRead = Schemas["JobRead"];
export type JobPublicRead = Schemas["JobPublicRead"];
/** Candidate-side info about their own application (editable while unengaged; the raw
 *  status is intentionally hidden from candidate payloads). */
export type MyApplicationInfo = Schemas["MyApplicationInfo"];

// Request bodies below stay hand-written: the FE deliberately constrains them beyond
// the generated types. `openapi-typescript` renders optional fields as `T | null`
// (so a form could send an explicit null the backend rejects) and required fields
// the FE flow fills with defaults. Keeping these tighter than the generated shapes
// is intentional — check them against `Schemas["JobCreate"]` / `Schemas["JobUpdate"]`
// / `Schemas["JobAdminCreate"]` when the backend changes.
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

/** Extends JobUpdate with is_featured. */
export interface JobAdminUpdate extends JobUpdate {
  is_featured?: boolean;
}

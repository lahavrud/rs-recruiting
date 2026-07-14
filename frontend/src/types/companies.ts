import type { CompanyProfileRead } from "@/types/auth";
import type { components } from "@/types/generated";

type Schemas = components["schemas"];

export type { CompanyProfileRead };

// Response/read DTOs aliased to the generated OpenAPI types (regenerated + diffed
// in CI). The self-update request body stays hand-written — the FE tightens its
// optional fields (generated renders them as `T | null`, a null the backend rejects).
export interface CompanyProfileSelfUpdate {
  name?: string;
  address?: string;
  contact_first_name?: string;
  contact_last_name?: string;
  contact_mobile_phone?: string;
  contact_landline_phone?: string | null;
}

export type CompanyStats = Schemas["CompanyStats"];
export type CompanyApplicationCandidateRead =
  Schemas["CompanyApplicationCandidateRead"];
export type CompanyApplicationRead = Schemas["CompanyApplicationRead"];
export type CompanyJobRecommendationRead = Schemas["CompanyJobRecommendationRead"];
export type PendingCompanyRead = Schemas["PendingCompanyRead"];
export type ApprovedCompanyRead = Schemas["ApprovedCompanyRead"];
export type ActiveCompanyRead = Schemas["ActiveCompanyRead"];

import type { UserRole } from "@/types/enums";
import type { components } from "@/types/generated";

type Schemas = components["schemas"];

// Response/read DTOs aliased to the generated OpenAPI types (regenerated + diffed
// in CI). Request bodies stay hand-written below — the FE tightens their optional
// fields (generated renders them as `T | null`, a null the backend rejects).
/** Backend schema is named AccessTokenResponse. */
export type TokenResponse = Schemas["AccessTokenResponse"];
export type UserRead = Schemas["UserRead"];
export type CompanyProfileRead = Schemas["CompanyProfileRead"];
export type UserWithCompanyRead = Schemas["UserWithCompanyRead"];

export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

/** Decoded JWT payload — client-side only, never sent over the wire. */
export interface JwtPayload {
  sub: string; // user id
  email: string;
  role: UserRole;
  exp: number;
}

/** Company fields nested in the register request body — not a standalone backend
 *  schema (it rides inside Body_register_auth_register_post), so it stays local. */
export interface CompanyProfileCreate {
  name: string;
  company_id: string;
  contact_first_name: string;
  contact_last_name: string;
  contact_mobile_phone: string;
  contact_landline_phone?: string | null;
}

export interface CompanyProfileAdminCreate {
  name: string;
  company_id: string;
  address: string;
  contact_email: string;
  contact_first_name: string;
  contact_last_name: string;
  contact_mobile_phone: string;
  contact_landline_phone?: string | null;
}

/** All fields optional. */
export interface CompanyProfileAdminUpdate {
  name?: string;
  company_id?: string;
  address?: string;
  contact_email?: string;
  contact_first_name?: string;
  contact_last_name?: string;
  contact_mobile_phone?: string;
  contact_landline_phone?: string | null;
}

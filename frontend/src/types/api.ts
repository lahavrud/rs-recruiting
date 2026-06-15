/**
 * Barrel re-export — all API types, grouped by domain.
 *
 * Existing `import ... from "@/types/api"` statements continue to work.
 * For new code, prefer importing directly from the domain file:
 *   import type { JobRead } from "@/types/jobs"
 */

export * from "@/types/enums";
export * from "@/types/audit";
export * from "@/types/auth";
export * from "@/types/jobs";
export * from "@/types/candidates";
export * from "@/types/companies";
export * from "@/types/invites";
export * from "@/types/health";

import type { components } from "@/types/generated";

type Schemas = components["schemas"];

// Aliased to the generated OpenAPI types (regenerated + diffed in CI).
export type AuditLogRead = Schemas["AuditLogRead"];
export type CandidateActivityEvent = Schemas["CandidateActivityEvent"];

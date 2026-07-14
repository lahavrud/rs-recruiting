import type { components } from "@/types/generated";

type Schemas = components["schemas"];

// Response/read DTOs aliased to the generated OpenAPI types (regenerated + diffed
// in CI).
export type InviteTokenRead = Schemas["InviteTokenRead"];
export type InviteMetadataPublic = Schemas["InviteMetadataPublic"];

export interface InviteTokenCreate {
  email: string;
}

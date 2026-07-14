import { describe, expect, it } from "vitest";

import {
  ApplicationStatus,
  InviteTokenStatus,
  JobStatus,
  UserRole,
} from "@/types/enums";
import {
  JOB_DESC_MAX,
  JOB_LOCATION_MAX,
  JOB_REQ_TEXT_MAX,
  JOB_SHORT_DESC_MAX,
  JOB_TITLE_MAX,
} from "@/types/jobs";

// Imported statically so the path resolves relative to this file (via vite), not
// to the process cwd — the test then works no matter where the runner is invoked.
import specJson from "../../../openapi.json";

/**
 * Parity guard for the runtime mirrors that `openapi-typescript` can't generate.
 *
 * The generated types (`generated.ts`) cover response/request *shapes*, but the
 * frontend also hand-maintains runtime *values* — enum const-objects and form
 * validation limits — because codegen emits types only. This test asserts those
 * values still match the committed OpenAPI spec, so drift on either side fails CI
 * (the spec itself is kept honest by the backend `export_openapi.py` diff gate).
 */

type SchemaProperty = { maxLength?: number; anyOf?: Array<{ maxLength?: number }> };

const spec = specJson as {
  components: {
    schemas: Record<
      string,
      { enum?: string[]; properties?: Record<string, SchemaProperty> }
    >;
  };
};

const schemas = spec.components.schemas;

/** Reads a field's maxLength whether it sits directly on the property (required
 *  fields) or inside an `anyOf` (nullable update fields render as `T | null`). */
function maxLengthOf(schemaName: string, field: string): number | undefined {
  const prop = schemas[schemaName]?.properties?.[field];
  if (prop?.maxLength != null) return prop.maxLength;
  return prop?.anyOf?.find((v) => v.maxLength != null)?.maxLength;
}

describe("enum parity with OpenAPI spec", () => {
  // FE const-object → backend schema name. Only enums that surface as a named
  // schema in the spec can be guarded here. `MatchSuggestionStatus` is
  // deliberately absent: it never appears on the OpenAPI surface (the match
  // endpoints take/return it inline as an action, not as a named schema), so
  // there is nothing in the spec to compare against — its backend↔FE parity is
  // the concern of the backend enum tests, not this contract gate.
  const cases: Array<[string, Record<string, string>]> = [
    ["ApplicationStatus", ApplicationStatus],
    ["JobStatus", JobStatus],
    ["UserRole", UserRole],
    ["InviteTokenStatus", InviteTokenStatus],
  ];

  it.each(cases)("%s members match the spec", (schemaName, feEnum) => {
    const specEnum = schemas[schemaName]?.enum;
    expect(specEnum, `${schemaName} missing from spec`).toBeDefined();
    expect([...(specEnum ?? [])].sort()).toEqual(Object.values(feEnum).sort());
  });
});

describe("validation limit parity with OpenAPI spec", () => {
  // The job-body constants back three write schemas (create / update / admin-
  // create) that all use the same named Python constant. Assert every constant
  // against every schema that carries the field, so a divergence in any one
  // schema — not just JobCreate — is caught.
  const bodyLimits: Array<[string, number, string]> = [
    ["JOB_TITLE_MAX", JOB_TITLE_MAX, "title"],
    ["JOB_LOCATION_MAX", JOB_LOCATION_MAX, "location"],
    ["JOB_DESC_MAX", JOB_DESC_MAX, "description"],
    ["JOB_SHORT_DESC_MAX", JOB_SHORT_DESC_MAX, "short_description"],
  ];
  const writeSchemas = ["JobCreate", "JobUpdate", "JobAdminCreate"];

  const cases: Array<[string, number, string, string]> = [
    ...bodyLimits.flatMap(([name, value, field]) =>
      writeSchemas.map(
        (schema) => [name, value, schema, field] as [string, number, string, string],
      ),
    ),
    ["JOB_REQ_TEXT_MAX", JOB_REQ_TEXT_MAX, "JobRequirementItem", "text"],
  ];

  it.each(cases)(
    "%s (=%s) matches %s.%s maxLength",
    (_name, feValue, schemaName, field) => {
      const specMax = maxLengthOf(schemaName, field);
      expect(
        specMax,
        `${schemaName}.${field}.maxLength missing from spec`,
      ).toBeDefined();
      expect(feValue).toBe(specMax);
    },
  );
});

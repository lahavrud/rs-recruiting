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

import { readFileSync } from "fs";
import { resolve } from "path";

/**
 * Parity guard for the runtime mirrors that `openapi-typescript` can't generate.
 *
 * The generated types (`generated.ts`) cover response/request *shapes*, but the
 * frontend also hand-maintains runtime *values* — enum const-objects and form
 * validation limits — because codegen emits types only. This test asserts those
 * values still match the committed OpenAPI spec, so drift on either side fails CI
 * (the spec itself is kept honest by the backend `export_openapi.py` diff gate).
 */

// vitest runs with cwd = frontend/ (both locally and in the CI frontend-checks
// job), where the committed spec lives. jsdom's `import.meta.url` is an http URL,
// so resolve from cwd rather than the module URL.
const spec = JSON.parse(
  readFileSync(resolve(process.cwd(), "openapi.json"), "utf-8"),
) as {
  components: {
    schemas: Record<
      string,
      { enum?: string[]; properties?: Record<string, { maxLength?: number }> }
    >;
  };
};

const schemas = spec.components.schemas;

describe("enum parity with OpenAPI spec", () => {
  // FE const-object → backend schema name. All four are part of the API surface,
  // so each must exist as a named schema with an `enum` in the spec.
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
  // FE constant → (schema, field) whose `maxLength` it mirrors.
  const cases: Array<[string, number, string, string]> = [
    ["JOB_TITLE_MAX", JOB_TITLE_MAX, "JobCreate", "title"],
    ["JOB_LOCATION_MAX", JOB_LOCATION_MAX, "JobCreate", "location"],
    ["JOB_DESC_MAX", JOB_DESC_MAX, "JobCreate", "description"],
    ["JOB_SHORT_DESC_MAX", JOB_SHORT_DESC_MAX, "JobCreate", "short_description"],
    ["JOB_REQ_TEXT_MAX", JOB_REQ_TEXT_MAX, "JobRequirementItem", "text"],
  ];

  it.each(cases)("%s matches %s.%s maxLength", (_name, feValue, schemaName, field) => {
    const specMax = schemas[schemaName]?.properties?.[field]?.maxLength;
    expect(specMax, `${schemaName}.${field}.maxLength missing from spec`).toBeDefined();
    expect(feValue).toBe(specMax);
  });
});

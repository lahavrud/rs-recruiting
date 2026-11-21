/**
 * Guards the #1182 fix: SortControl options can name a full sort chain, so the
 * Applications "status, newest/oldest first" options keep status asc and set
 * the date order they describe.
 */
import { describe, expect, it } from "vitest";

import {
  findActiveOption,
  formatSortValue,
  parseSortValue,
} from "@/components/admin/sortControlUtils";

const OPTIONS = [
  { value: "status:asc,created_at:desc", label: "status, newest" },
  { value: "status:asc,created_at:asc", label: "status, oldest" },
  { value: "created_at:desc", label: "newest" },
  { value: "name:asc", label: "a-z" },
];

describe("parseSortValue", () => {
  it("parses a single key", () => {
    expect(parseSortValue("name:asc")).toEqual([{ column: "name", order: "asc" }]);
  });

  it("parses a primary + secondary chain", () => {
    expect(parseSortValue("status:asc,created_at:desc")).toEqual([
      { column: "status", order: "asc" },
      { column: "created_at", order: "desc" },
    ]);
  });

  it("round-trips through formatSortValue", () => {
    const value = "status:asc,created_at:asc";
    expect(formatSortValue(parseSortValue(value))).toBe(value);
  });
});

describe("findActiveOption", () => {
  it("matches the page's default chain exactly (status asc, newest first)", () => {
    expect(findActiveOption(OPTIONS, "status:asc,created_at:desc")?.label).toBe(
      "status, newest",
    );
    expect(findActiveOption(OPTIONS, "status:asc,created_at:asc")?.label).toBe(
      "status, oldest",
    );
  });

  it("matches a single-key value", () => {
    expect(findActiveOption(OPTIONS, "name:asc")?.label).toBe("a-z");
  });

  it("falls back to the primary key for a chain built from desktop headers", () => {
    expect(findActiveOption(OPTIONS, "created_at:desc,status:asc")?.label).toBe(
      "newest",
    );
  });

  it("returns undefined when nothing matches", () => {
    expect(findActiveOption(OPTIONS, "name:desc")).toBeUndefined();
  });
});

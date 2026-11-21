import type { SortOrder } from "@/hooks/useColumnSort";

export interface ParsedSortKey {
  column: string;
  order: SortOrder;
}

/**
 * Parse a `SortControl` option value into its sort keys. A value is one or
 * more comma-separated `"<column>:<order>"` pairs, primary first — e.g.
 * `"status:asc,created_at:desc"` sorts by status, then newest-first within
 * each status.
 */
export function parseSortValue(value: string): ParsedSortKey[] {
  return value.split(",").map((pair) => {
    const [column, order] = pair.split(":");
    return { column, order: order as SortOrder };
  });
}

/** Serialize sort keys back to a `SortControl` value. */
export function formatSortValue(keys: readonly ParsedSortKey[]): string {
  return keys.map((key) => `${key.column}:${key.order}`).join(",");
}

/**
 * The option to show as active: an exact match on the whole chain, else the
 * first option whose primary key matches — so a chain built by clicking
 * desktop headers (e.g. status ↓ then date) still shows a sensible label in
 * the compact rail.
 */
export function findActiveOption<T extends { value: string }>(
  options: readonly T[],
  value: string,
): T | undefined {
  const primary = (v: string) => v.split(",")[0];
  return (
    options.find((option) => option.value === value) ??
    options.find((option) => primary(option.value) === primary(value))
  );
}

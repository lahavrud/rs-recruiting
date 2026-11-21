/**
 * Guards the #1181 fix: the mobile sort dropdown applies the exact option the
 * user picked (`set`), while desktop headers keep flip-on-reclick (`toggle`).
 */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useColumnSort } from "@/hooks/useColumnSort";

const INITIAL = { column: "created_at" as const, order: "desc" as const };

function setup() {
  return renderHook(() => useColumnSort<"name" | "created_at">(INITIAL));
}

describe("useColumnSort", () => {
  it("set: re-selecting the active option keeps its direction", () => {
    const { result } = setup();
    act(() => result.current.set("created_at", "desc"));
    expect(result.current).toMatchObject({ sort: "created_at", order: "desc" });
  });

  it("set: picking the same option twice applies it both times", () => {
    const { result } = setup();
    act(() => result.current.set("name", "asc"));
    act(() => result.current.set("name", "asc"));
    expect(result.current).toMatchObject({ sort: "name", order: "asc" });
  });

  it("set: applies an explicit direction on the active column", () => {
    const { result } = setup();
    act(() => result.current.set("created_at", "asc"));
    expect(result.current).toMatchObject({ sort: "created_at", order: "asc" });
  });

  it("toggle: flips the active column and uses natural order for a new one", () => {
    const { result } = setup();
    act(() => result.current.toggle("created_at", "desc"));
    expect(result.current).toMatchObject({ sort: "created_at", order: "asc" });
    act(() => result.current.toggle("name", "asc"));
    expect(result.current).toMatchObject({ sort: "name", order: "asc" });
  });
});

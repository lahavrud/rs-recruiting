/**
 * `replace` sets a whole chain (mobile dropdown, #1182); `click` keeps the
 * desktop header cycle.
 */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSortChain } from "@/hooks/useSortChain";

type Col = "name" | "created_at" | "status";

function setup() {
  return renderHook(() =>
    useSortChain<Col>([
      { column: "status", order: "asc" },
      { column: "created_at", order: "desc" },
    ]),
  );
}

describe("useSortChain.replace", () => {
  it("sets a primary + secondary chain", () => {
    const { result } = setup();
    act(() =>
      result.current.replace([
        { column: "status", order: "asc" },
        { column: "created_at", order: "asc" },
      ]),
    );
    expect(result.current.chain).toEqual([
      { column: "status", order: "asc" },
      { column: "created_at", order: "asc" },
    ]);
  });

  it("collapses to a single key", () => {
    const { result } = setup();
    act(() => result.current.replace([{ column: "name", order: "desc" }]));
    expect(result.current.chain).toEqual([{ column: "name", order: "desc" }]);
  });

  it("caps the chain at 2 keys and ignores an empty chain", () => {
    const { result } = setup();
    act(() =>
      result.current.replace([
        { column: "name", order: "asc" },
        { column: "status", order: "asc" },
        { column: "created_at", order: "desc" },
      ]),
    );
    expect(result.current.chain).toHaveLength(2);
    act(() => result.current.replace([]));
    expect(result.current.chain).toHaveLength(2);
  });
});

describe("useSortChain.click", () => {
  it("flips, then removes, a column in a 2-key chain", () => {
    const { result } = setup();
    act(() => result.current.click("status", "asc"));
    expect(result.current.chain[0]).toEqual({ column: "status", order: "desc" });
    act(() => result.current.click("status", "asc"));
    expect(result.current.chain).toEqual([{ column: "created_at", order: "desc" }]);
  });
});

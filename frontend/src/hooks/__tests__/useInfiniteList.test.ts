/**
 * Guards the #1180 fix: when the fetcher changes (sort/filter) while a request
 * is still in flight, the new fetcher's first page must load and win, and the
 * stale response — including its cursor, minted under the old sort — must be
 * discarded.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type CursorPage, useInfiniteList } from "@/hooks/useInfiniteList";

interface Pending {
  cursor: string | null;
  resolve: (page: CursorPage<string>) => void;
}

/** A fetcher whose calls stay pending until the test resolves them. */
function deferredFetcher() {
  const calls: Pending[] = [];
  const fetcher = vi.fn(
    (cursor: string | null) =>
      new Promise<CursorPage<string>>((resolve) => {
        calls.push({ cursor, resolve });
      }),
  );
  return { fetcher, calls };
}

let observerCallback: IntersectionObserverCallback | null = null;

class IntersectionObserverStub {
  constructor(cb: IntersectionObserverCallback) {
    observerCallback = cb;
  }
  observe() {}
  disconnect() {}
  unobserve() {}
  takeRecords() {
    return [];
  }
}

/** Simulate the bottom-of-list sentinel scrolling into view. */
function reachSentinel() {
  act(() => {
    observerCallback?.(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
  });
}

beforeEach(() => {
  observerCallback = null;
  vi.stubGlobal("IntersectionObserver", IntersectionObserverStub);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useInfiniteList", () => {
  it("loads the new fetcher's first page when the fetcher changes mid-request", async () => {
    const byName = deferredFetcher();
    const byNameDesc = deferredFetcher();
    const { result, rerender } = renderHook(({ f }) => useInfiniteList(f), {
      initialProps: { f: byName.fetcher },
    });
    expect(byName.calls).toHaveLength(1);

    // Second header click before the first response lands.
    rerender({ f: byNameDesc.fetcher });
    expect(byNameDesc.fetcher).toHaveBeenCalledWith(null);

    // Stale response arrives last — it must not overwrite the new one.
    await act(async () => {
      byNameDesc.calls[0].resolve({ items: ["z", "a"], next_cursor: null });
    });
    await act(async () => {
      byName.calls[0].resolve({ items: ["a", "z"], next_cursor: "stale" });
    });

    expect(result.current.items).toEqual(["z", "a"]);
    expect(result.current.hasMore).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });

  it("discards an in-flight load-more page and its cursor when the fetcher changes", async () => {
    const byStatus = deferredFetcher();
    const byName = deferredFetcher();
    const { result, rerender } = renderHook(({ f }) => useInfiniteList(f), {
      initialProps: { f: byStatus.fetcher },
    });
    act(() => result.current.sentinelRef(document.createElement("div")));
    await act(async () => {
      byStatus.calls[0].resolve({ items: ["s1"], next_cursor: "status-c1" });
    });

    // Scroll to the bottom → page 2 of the old sort starts loading.
    reachSentinel();
    expect(byStatus.calls[1].cursor).toBe("status-c1");

    // Sort changes while page 2 is in flight.
    rerender({ f: byName.fetcher });
    expect(byName.fetcher).toHaveBeenCalledWith(null);

    await act(async () => {
      byStatus.calls[1].resolve({ items: ["s2"], next_cursor: "status-c2" });
    });
    await act(async () => {
      byName.calls[0].resolve({ items: ["n1"], next_cursor: "name-c1" });
    });
    expect(result.current.items).toEqual(["n1"]);

    // The next load-more must use the new sort's cursor, never the stale one.
    reachSentinel();
    await waitFor(() => expect(byName.calls).toHaveLength(2));
    expect(byName.calls[1].cursor).toBe("name-c1");
    expect(byStatus.fetcher).toHaveBeenCalledTimes(2);
  });

  it("ignores an error from a superseded request", async () => {
    const calls: { reject: (e: Error) => void }[] = [];
    const failing = vi.fn(
      () =>
        new Promise<CursorPage<string>>((_, reject) => {
          calls.push({ reject });
        }),
    );
    const fresh = deferredFetcher();
    const { result, rerender } = renderHook(({ f }) => useInfiniteList(f), {
      initialProps: { f: failing as (c: string | null) => Promise<CursorPage<string>> },
    });
    rerender({ f: fresh.fetcher });
    await act(async () => {
      fresh.calls[0].resolve({ items: ["ok"], next_cursor: null });
    });
    await act(async () => {
      calls[0].reject(new Error("stale"));
    });

    expect(result.current.error).toBeNull();
    expect(result.current.items).toEqual(["ok"]);
  });

  it("still ignores a second load-more while one is in flight", async () => {
    const { fetcher, calls } = deferredFetcher();
    const { result } = renderHook(() => useInfiniteList(fetcher));
    act(() => result.current.sentinelRef(document.createElement("div")));
    await act(async () => {
      calls[0].resolve({ items: ["a"], next_cursor: "c1" });
    });

    reachSentinel();
    reachSentinel();
    expect(calls).toHaveLength(2);

    await act(async () => {
      calls[1].resolve({ items: ["b"], next_cursor: null });
    });
    expect(result.current.items).toEqual(["a", "b"]);
  });
});

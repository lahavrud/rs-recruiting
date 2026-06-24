import { useEffect, useRef } from "react";

/**
 * Scrolls a rail row into view once the row matching `selectedId` mounts.
 * `items` is in the dependency list so a selection that lands before its
 * row has loaded (still paging via `useInfiniteList`) still scrolls once
 * the row actually appears, instead of being silently dropped.
 *
 * Returns a ref-callback factory — call it per-row with that row's id.
 */
export function useScrollSelectedIntoView<T>(
  selectedId: number | null | undefined,
  items: T[],
) {
  const rowRefs = useRef(new Map<number, HTMLElement>());

  useEffect(() => {
    if (selectedId == null) return;
    rowRefs.current.get(selectedId)?.scrollIntoView({ block: "nearest" });
  }, [selectedId, items]);

  return (id: number) => (node: HTMLElement | null) => {
    if (node) rowRefs.current.set(id, node);
    else rowRefs.current.delete(id);
  };
}

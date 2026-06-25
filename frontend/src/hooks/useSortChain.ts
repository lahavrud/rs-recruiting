import { useCallback, useRef, useState } from "react";

import type { SortOrder } from "@/hooks/useColumnSort";

export interface SortKey<TColumn extends string> {
  column: TColumn;
  order: SortOrder;
}

/**
 * Up-to-2-key sort state for building a cross-sort by clicking column
 * headers in sequence — e.g. click "Status" then "Date" to sort by status,
 * then by date within each status group.
 *
 * Each column cycles through 3 clicks: natural order → toggled direction →
 * off (removed from the chain). When the last remaining column is removed,
 * the chain resets to the initial defaults rather than leaving a stuck
 * single-column state.
 *
 * - Clicking a column not yet in the chain adds it: as the new sole column
 *   if the chain was empty or already had 2 (unrelated) columns, or as the
 *   secondary if the chain has exactly 1 (different) column — the
 *   first-clicked column stays primary.
 */
export function useSortChain<TColumn extends string>(
  initial: SortKey<TColumn> | SortKey<TColumn>[],
) {
  const initialChain = Array.isArray(initial) ? initial : [initial];
  const initialRef = useRef(initialChain);
  const [chain, setChain] = useState<SortKey<TColumn>[]>(initialChain);

  const click = useCallback((column: TColumn, naturalOrder: SortOrder) => {
    setChain((prev) => {
      const idx = prev.findIndex((key) => key.column === column);
      if (idx !== -1) {
        const isToggled = prev[idx].order !== naturalOrder;
        if (isToggled) {
          if (prev.length > 1) {
            return prev.filter((_, i) => i !== idx);
          }
          return initialRef.current;
        }
        return prev.map((key, i) =>
          i === idx ? { ...key, order: key.order === "asc" ? "desc" : "asc" } : key,
        );
      }
      if (prev.length === 1) {
        return [...prev, { column, order: naturalOrder }];
      }
      return [{ column, order: naturalOrder }];
    });
  }, []);

  /** Collapse to a single-column sort — used by the mobile dropdown. */
  const replace = useCallback((column: TColumn, order: SortOrder) => {
    setChain([{ column, order }]);
  }, []);

  return { chain, click, replace };
}

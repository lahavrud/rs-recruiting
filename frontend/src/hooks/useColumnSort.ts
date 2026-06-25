import { useCallback, useState } from "react";

export type SortOrder = "asc" | "desc";

/**
 * Column + direction sort state shared by every admin list page's sortable
 * table headers and mobile sort dropdown. Clicking the already-active column
 * flips its direction; switching column resets to that column's natural
 * default (e.g. alphabetical-ascending for a name column, newest-first for a
 * date column).
 */
export function useColumnSort<TColumn extends string>(initial: {
  column: TColumn;
  order: SortOrder;
}) {
  const [state, setState] = useState(initial);

  const toggle = useCallback((column: TColumn, naturalOrder: SortOrder) => {
    setState((prev) =>
      prev.column === column
        ? { column, order: prev.order === "asc" ? "desc" : "asc" }
        : { column, order: naturalOrder },
    );
  }, []);

  return { sort: state.column, order: state.order, toggle };
}

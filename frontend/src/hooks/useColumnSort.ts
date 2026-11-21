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

  /**
   * Apply an explicit column + direction — for the mobile `SortControl`, whose
   * options each name a full sort. Unlike `toggle`, re-selecting the active
   * option is a no-op instead of flipping the direction (#1181).
   */
  const set = useCallback((column: TColumn, order: SortOrder) => {
    setState({ column, order });
  }, []);

  return { sort: state.column, order: state.order, toggle, set };
}

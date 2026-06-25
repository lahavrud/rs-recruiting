import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Server response shape produced by the backend's `CursorPage[T]` envelope
 * (see `src/core/infrastructure/pagination.py`).
 */
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}

export type CursorFetcher<T> = (cursor: string | null) => Promise<CursorPage<T>>;

export interface UseInfiniteListResult<T> {
  items: T[];
  isLoading: boolean;
  isFetchingMore: boolean;
  hasMore: boolean;
  error: Error | null;
  /** Attach to a sentinel element at the bottom of the list. */
  sentinelRef: (node: HTMLElement | null) => void;
  /** Re-fetch the first page. Useful after mutations or filter changes. */
  reload: () => void;
  /** Append a single item to the head of the list. */
  prependItem: (item: T) => void;
  /**
   * Replace one matching item. Pass either the full new item, or an updater
   * function that receives the current item — use the function form when only
   * a few fields change so joined/derived fields aren't lost.
   */
  updateItem: (predicate: (item: T) => boolean, next: T | ((prev: T) => T)) => void;
  /** Remove all items matching a predicate. */
  removeItem: (predicate: (item: T) => boolean) => void;
}

interface State<T> {
  items: T[];
  cursor: string | null;
  hasMore: boolean;
  isLoading: boolean;
  isFetchingMore: boolean;
  error: Error | null;
}

function initialState<T>(): State<T> {
  return {
    items: [],
    cursor: null,
    hasMore: true,
    isLoading: true,
    isFetchingMore: false,
    error: null,
  };
}

/**
 * Cursor-paginated infinite list driven by an `IntersectionObserver` sentinel.
 *
 * Memoize your fetcher with `useCallback` and depend on filter values — the
 * hook resets and refetches whenever the fetcher identity changes.
 */
export function useInfiniteList<T>(
  fetcher: CursorFetcher<T>,
): UseInfiniteListResult<T> {
  const [state, setState] = useState<State<T>>(initialState);

  const fetcherRef = useRef(fetcher);
  const inFlight = useRef(false);
  const stateRef = useRef(state);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const fetchPage = useCallback(
    async (
      nextCursor: string | null,
      replace: boolean,
      showLoading = true,
    ): Promise<void> => {
      if (inFlight.current) return;
      inFlight.current = true;
      setState((prev) =>
        replace
          ? { ...prev, isLoading: showLoading, error: null }
          : { ...prev, isFetchingMore: true, error: null },
      );
      try {
        const page = await fetcherRef.current(nextCursor);
        setState((prev) => ({
          ...prev,
          items: replace ? page.items : [...prev.items, ...page.items],
          cursor: page.next_cursor,
          hasMore: page.next_cursor != null,
          isLoading: false,
          isFetchingMore: false,
          error: null,
        }));
      } catch (err) {
        const wrapped = err instanceof Error ? err : new Error(String(err));
        setState((prev) => ({
          ...prev,
          isLoading: false,
          isFetchingMore: false,
          error: wrapped,
        }));
      } finally {
        inFlight.current = false;
      }
    },
    [],
  );

  // Reset + load whenever the fetcher identity changes (filters/sort/page
  // mount). Keep the previous items visible until the new page arrives —
  // if we already have items (e.g. toggling sort), skip the loading state
  // entirely so the list swaps in place instead of flashing to a skeleton.
  useEffect(() => {
    const hadItems = stateRef.current.items.length > 0;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((prev) => ({ ...initialState<T>(), items: prev.items }));
    void fetchPage(null, true, !hadItems);
  }, [fetcher, fetchPage]);

  // Observer for the bottom-of-list sentinel.
  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useCallback(
    (node: HTMLElement | null) => {
      observerRef.current?.disconnect();
      observerRef.current = null;
      if (!node) return;
      const observer = new IntersectionObserver(
        (entries) => {
          if (!entries[0]?.isIntersecting || inFlight.current) return;
          const current = stateRef.current;
          if (current.hasMore && current.cursor != null) {
            void fetchPage(current.cursor, false);
          }
        },
        { rootMargin: "200px 0px" },
      );
      observer.observe(node);
      observerRef.current = observer;
    },
    [fetchPage],
  );

  useEffect(
    () => () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
    },
    [],
  );

  const reload = useCallback(() => {
    const hadItems = stateRef.current.items.length > 0;
    setState((prev) => ({ ...initialState<T>(), items: prev.items }));
    void fetchPage(null, true, !hadItems);
  }, [fetchPage]);

  const prependItem = useCallback((item: T) => {
    setState((prev) => ({ ...prev, items: [item, ...prev.items] }));
  }, []);

  const updateItem = useCallback(
    (predicate: (item: T) => boolean, next: T | ((prev: T) => T)) => {
      setState((prev) => ({
        ...prev,
        items: prev.items.map((item) =>
          predicate(item)
            ? typeof next === "function"
              ? (next as (p: T) => T)(item)
              : next
            : item,
        ),
      }));
    },
    [],
  );

  const removeItem = useCallback((predicate: (item: T) => boolean) => {
    setState((prev) => ({
      ...prev,
      items: prev.items.filter((item) => !predicate(item)),
    }));
  }, []);

  // Defensive: if React ever hands back undefined initial state in a
  // pathological reload, fall back to safe defaults rather than crashing
  // the host component.
  const items = state?.items ?? [];

  return {
    items,
    isLoading: state?.isLoading ?? true,
    isFetchingMore: state?.isFetchingMore ?? false,
    hasMore: state?.hasMore ?? false,
    error: state?.error ?? null,
    sentinelRef,
    reload,
    prependItem,
    updateItem,
    removeItem,
  };
}

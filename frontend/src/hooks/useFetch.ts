import { useEffect, useRef, useState } from "react";

export interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: unknown;
}

interface State<T> {
  data: T | null;
  loading: boolean;
  error: unknown;
}

function initialState<T>(): State<T> {
  return { data: null, loading: true, error: null };
}

/**
 * Runs an async fetch on mount (and whenever `deps` changes), guarding
 * against setting state after the effect has been cleaned up. Replaces the
 * repeated `let alive = true; (async () => {...})(); return () => { alive
 * = false }` boilerplate found across one-shot detail/profile fetches.
 *
 * The raw thrown value is exposed as `error` so callers can still branch on
 * its shape (e.g. `axios.isAxiosError(error) && error.response?.status ===
 * 404`) to pick a Hebrew error message — this hook only owns the
 * loading/unmount bookkeeping, not error-message mapping.
 *
 * Pass `enabled=false` to skip the fetch entirely (e.g. a component that
 * renders for every role but may only call an endpoint for some of them); the
 * result stays idle (`data: null, loading: false`) until it flips true.
 *
 * Not for paginated/list fetching — use `useInfiniteList` for that.
 */
export function useFetch<T>(
  fn: () => Promise<T>,
  deps: unknown[],
  enabled = true,
): UseFetchResult<T> {
  const [state, setState] = useState<State<T>>(() => ({
    data: null,
    loading: enabled,
    error: null,
  }));
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    if (!enabled) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({ data: null, loading: false, error: null });
      return;
    }
    let alive = true;
    setState(initialState<T>());
    (async () => {
      try {
        const data = await fnRef.current();
        if (alive) setState({ data, loading: false, error: null });
      } catch (error) {
        if (alive) setState({ data: null, loading: false, error });
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled]);

  return state;
}

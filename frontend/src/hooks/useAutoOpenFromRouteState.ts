import { useEffect } from "react";

import { useLocation, useNavigate } from "react-router-dom";

/**
 * Reads a typed value from React Router navigation state, calls openFn with
 * it, then clears the state so a back-navigation doesn't re-open the panel.
 *
 * Replaces the eslint-disable react-hooks/set-state-in-effect pattern at
 * call sites that auto-open a detail panel from `location.state`.
 */
export function useAutoOpenFromRouteState<T>(
  stateKey: string,
  openFn: (value: T) => void,
): void {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const value = (location.state as Record<string, T> | null)?.[stateKey];
    if (value === undefined) return;
    openFn(value);
    navigate(location.pathname + location.search, { replace: true, state: null });
  }, [location.state, location.pathname, location.search, navigate, stateKey, openFn]);
}

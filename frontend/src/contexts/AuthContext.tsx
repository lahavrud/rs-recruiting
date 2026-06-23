import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import * as Sentry from "@sentry/react";

import { login as loginService, logout as logoutService, refreshTokens } from "@/services/auth";
import type { LoginRequest } from "@/types/auth";
import type { UserRole } from "@/types/enums";
import { getToken, inspectToken, removeToken } from "@/utils/token";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
}

export interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  /** True while the initial refresh-token probe is in flight (page load with
   *  expired access token). Route guards render null instead of redirecting. */
  isInitializing: boolean;
  /** True while logout is in progress. Route guards render null instead of
   *  redirecting so the page-replacement completes without a /login flash. */
  isLoggingOut: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextType | null>(null);

function payloadToUser(payload: {
  sub: string;
  email: string;
  role: UserRole;
}): AuthUser {
  return { id: payload.sub, email: payload.email, role: payload.role };
}

/**
 * Compute the initial auth state from localStorage in one pass.
 *
 * Three cases:
 *  - No token:       user=null, isInitializing=false  (never logged in — skip probe)
 *  - Valid token:    user=AuthUser, isInitializing=false (no probe needed)
 *  - Expired token:  user=null, isInitializing=true   (had a session — probe the cookie)
 *
 * Expired tokens are intentionally NOT removed here so this function stays
 * side-effect-free and safe to call twice in React Strict Mode. The probe
 * effect's .catch() clears the token if refresh fails.
 */
function computeInitialAuth(): { user: AuthUser | null; isInitializing: boolean } {
  const token = getToken();
  if (!token) return { user: null, isInitializing: false };
  const inspection = inspectToken(token);
  if (inspection.status === "valid") {
    return { user: payloadToUser(inspection.payload), isInitializing: false };
  }
  if (inspection.status === "expired") {
    return { user: null, isInitializing: true };
  }
  // Invalid/malformed token — clean it up immediately
  removeToken();
  return { user: null, isInitializing: false };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Single lazy initializer so getToken() is read exactly once
  const [{ user: initUser, isInitializing: initIsInitializing }] =
    useState(computeInitialAuth);
  const [user, setUser] = useState<AuthUser | null>(initUser);
  const [isInitializing, setIsInitializing] = useState(initIsInitializing);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const logoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (logoutTimerRef.current !== null) clearTimeout(logoutTimerRef.current);
    };
  }, []);

  // Silent refresh on mount: only fires when an expired access token was found
  // (isInitializing=true). Removes the expired token immediately so it never lingers
  // in localStorage regardless of whether the probe completes or is aborted
  // (e.g. React 18 Strict Mode double-mount, SPA navigation away mid-fetch).
  // refreshTokens will call setToken on success, restoring a valid token.
  //
  // Safety valve: if the network never responds (stalled proxy, partition),
  // we must still unblock the UI — otherwise every route guard renders null
  // indefinitely. Mirrors the 500 ms safety valve used by the logout flow.
  useEffect(() => {
    if (!isInitializing) return;
    removeToken(); // expired token served its purpose as a "had session" marker
    const controller = new AbortController();
    const safetyTimer = setTimeout(() => setIsInitializing(false), 10_000);

    refreshTokens(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        const inspection = inspectToken(response.access_token);
        if (inspection.status === "valid") {
          setUser(payloadToUser(inspection.payload));
        } else {
          // Server issued a token that appears invalid/expired locally (extreme clock
          // skew). Remove it so computeInitialAuth won't find it on the next mount
          // and re-enter the probe loop.
          removeToken();
        }
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        // Token already removed above; nothing further to clean up.
      })
      .finally(() => {
        clearTimeout(safetyTimer);
        if (!controller.signal.aborted) setIsInitializing(false);
      });

    return () => {
      controller.abort();
      clearTimeout(safetyTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (user) {
      Sentry.setUser({ id: user.id, role: user.role });
    } else {
      Sentry.setUser(null);
    }
  }, [user]);

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await loginService(credentials);
    const inspection = inspectToken(response.access_token);

    if (inspection.status !== "valid") {
      logoutService();
      throw new Error("Authentication failed: invalid access token");
    }

    setUser(payloadToUser(inspection.payload));
  }, []);

  const logout = useCallback(() => {
    // Set isLoggingOut first so route guards render null instead of redirecting to
    // /login — prevents a flash of the login page while the browser replaces the
    // document.  After that, clear tokens and user state before navigating so
    // guards never see a stale "logged-in" user if the redirect stalls.
    setIsLoggingOut(true);
    logoutService();
    setUser(null);
    window.location.replace("/");
    // Safety valve: if navigation is blocked (e.g. browser extension), reset
    // the sentinel so route guards can fall through to /login on their own.
    logoutTimerRef.current = setTimeout(() => setIsLoggingOut(false), 500);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      isInitializing,
      isLoggingOut,
      login,
      logout,
    }),
    [user, isInitializing, isLoggingOut, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

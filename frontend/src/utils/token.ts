import { jwtDecode } from "jwt-decode";

import type { JwtPayload } from "@/types/auth";
const ACCESS_TOKEN_KEY = "access_token";

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export type TokenInspection =
  | { status: "valid"; payload: JwtPayload }
  | { status: "expired" }
  | { status: "invalid" };

/**
 * Decode a JWT token without side-effects.
 * Unlike decodeToken(), never removes the token from storage.
 * Use this for freshly-received server tokens or when the caller
 * wants to decide what to do on expiry/failure.
 */
export function inspectToken(token: string): TokenInspection {
  try {
    const payload = jwtDecode<JwtPayload>(token);
    if (typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) {
      return { status: "invalid" };
    }
    if (payload.exp * 1000 < Date.now()) {
      return { status: "expired" };
    }
    return { status: "valid", payload };
  } catch {
    return { status: "invalid" };
  }
}

/**
 * Decode a JWT token string and clean up localStorage on failure.
 *
 * Returns the decoded payload when the token is valid, or `null` when the
 * token is expired or malformed — **and calls `removeToken()` as a
 * side-effect in the null case**.
 *
 * Use this only when you want the "read + auto-cleanup" behaviour, e.g.
 * reading an access token that was loaded from localStorage and should be
 * purged if stale. For side-effect-free inspection (e.g. a freshly-issued
 * server token, or a token passed as an argument), use `inspectToken` instead.
 */
export function decodeToken(token: string): JwtPayload | null {
  const result = inspectToken(token);
  if (result.status === "valid") return result.payload;
  removeToken();
  return null;
}

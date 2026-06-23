import api from "@/services/api";
import type { LoginRequest, TokenResponse, UserWithCompanyRead } from "@/types/auth";
import type { InviteMetadataPublic } from "@/types/invites";
import { getToken, removeToken, setToken } from "@/utils/token";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  // withCredentials required cross-origin so the browser stores the Set-Cookie
  // refresh_token from the response (same reasoning as refreshTokens below).
  const response = await api.post<TokenResponse>("/auth/login", credentials, {
    withCredentials: true,
  });
  setToken(response.data.access_token);
  return response.data;
}

export async function register(
  formData: FormData,
  inviteToken: string,
): Promise<UserWithCompanyRead> {
  const response = await api.post<UserWithCompanyRead>("/auth/register", formData, {
    params: { token: inviteToken },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function refreshTokens(signal?: AbortSignal): Promise<TokenResponse> {
  // Refresh token is an HttpOnly cookie — requires withCredentials for cross-origin
  // requests (e.g. frontend on app.* and API on api.* subdomain in production).
  const response = await api.post<TokenResponse>("/auth/refresh", null, {
    signal,
    withCredentials: true,
  });
  setToken(response.data.access_token);
  return response.data;
}

export async function getInviteMetadata(token: string): Promise<InviteMetadataPublic> {
  const res = await api.get<InviteMetadataPublic>(`/auth/invite/${token}`);
  return res.data;
}

export async function activateAccount(token: string): Promise<void> {
  await api.post(`/auth/activate`, null, {
    params: { token },
  });
}

export interface CandidateRegisterPayload {
  email: string;
  password: string;
  full_name: string;
  privacy_accepted: boolean;
  terms_accepted: boolean;
}

export async function registerCandidate(
  payload: CandidateRegisterPayload,
): Promise<void> {
  await api.post("/auth/candidate/register", payload);
}

export async function resendCandidateActivation(email: string): Promise<void> {
  await api.post("/auth/candidate/resend-activation", { email });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await api.post("/auth/forgot-password", { email });
}

export async function validateResetToken(token: string): Promise<void> {
  await api.get("/auth/reset-password/validate", { params: { token } });
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await api.post("/auth/reset-password", {
    token,
    new_password: newPassword,
  });
}

export function logout(): void {
  // Capture access token BEFORE clearing — the server endpoint requires it for
  // auth. The refresh token is an HttpOnly cookie sent automatically by the
  // browser; the server clears it via Set-Cookie on the response.
  const accessToken = getToken();
  removeToken();
  // Best-effort server-side revocation. We use `fetch` with `keepalive: true`
  // instead of axios so the request survives the navigation that almost
  // always follows logout() — otherwise Firefox cancels it mid-flight and
  // logs `NS_BINDING_ABORTED`.
  const baseURL = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? "");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  try {
    void fetch(`${baseURL}/auth/logout`, {
      method: "POST",
      keepalive: true,
      // "include" (not "same-origin") so the refresh cookie is sent cross-origin
      // in production, allowing the server to delete the RefreshToken row.
      credentials: "include",
      headers,
    }).catch(() => {});
  } catch {
    // sendBeacon-style fire-and-forget — swallow sync errors too
  }
}

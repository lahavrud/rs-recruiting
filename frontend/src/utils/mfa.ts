import axios from "axios";

/** Digits in an authenticator (TOTP) code. */
export const TOTP_LENGTH = 6;
const SECONDS_PER_MINUTE = 60;

/**
 * Keep only the digits of a typed or pasted authenticator code, capped at
 * its length. Apps show codes as "123 456"; a `maxLength` on the raw input
 * would cut that paste to "123 45".
 */
export function normalizeTotp(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, TOTP_LENGTH);
}

/** Status and backend `detail` code of an API error (both optional). */
export function apiErrorInfo(error: unknown): { status?: number; detail?: string } {
  if (!axios.isAxiosError(error)) return {};
  const detail = error.response?.data?.detail;
  return {
    status: error.response?.status,
    detail: typeof detail === "string" ? detail : undefined,
  };
}

/** Whole minutes left on a lock, from a 429's `Retry-After` (seconds). */
export function retryAfterMinutes(error: unknown): number | null {
  if (!axios.isAxiosError(error)) return null;
  const seconds = Number(error.response?.headers?.["retry-after"]);
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / SECONDS_PER_MINUTE) : null;
}

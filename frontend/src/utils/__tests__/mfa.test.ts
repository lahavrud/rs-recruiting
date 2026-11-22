import { AxiosError, AxiosHeaders } from "axios";

import { apiErrorInfo, normalizeTotp, retryAfterMinutes } from "@/utils/mfa";

function apiError(status: number, data: unknown, headers: Record<string, string> = {}) {
  return new AxiosError("fail", "ERR", undefined, undefined, {
    status,
    statusText: "",
    headers,
    config: { headers: new AxiosHeaders() },
    data,
  });
}

describe("normalizeTotp", () => {
  it("keeps digits only, capped at six", () => {
    expect(normalizeTotp("123 456")).toBe("123456");
    expect(normalizeTotp(" 12-34 56 78")).toBe("123456");
    expect(normalizeTotp("abc")).toBe("");
  });
});

describe("apiErrorInfo", () => {
  it("reads status and a string detail", () => {
    expect(apiErrorInfo(apiError(401, { detail: "invalid_mfa_code" }))).toEqual({
      status: 401,
      detail: "invalid_mfa_code",
    });
  });

  it("ignores non-string details and non-axios errors", () => {
    expect(apiErrorInfo(apiError(422, { detail: [{ msg: "x" }] }))).toEqual({
      status: 422,
      detail: undefined,
    });
    expect(apiErrorInfo(new Error("x"))).toEqual({});
  });
});

describe("retryAfterMinutes", () => {
  it("rounds Retry-After seconds up to whole minutes", () => {
    const fiveMinutes = 5; // Retry-After 300 s
    expect(retryAfterMinutes(apiError(429, {}, { "retry-after": "300" }))).toBe(fiveMinutes);
    expect(retryAfterMinutes(apiError(429, {}, { "retry-after": "61" }))).toBe(2);
  });

  it("is null without a usable header", () => {
    expect(retryAfterMinutes(apiError(429, {}))).toBeNull();
    expect(retryAfterMinutes(apiError(429, {}, { "retry-after": "soon" }))).toBeNull();
    expect(retryAfterMinutes(new Error("x"))).toBeNull();
  });
});

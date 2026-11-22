import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { vi } from "vitest";

import api, { MFA_SETUP_PATH } from "@/services/api";

/** Make every request through `api` fail with this status + detail. */
function failWith(status: number, detail: string) {
  api.defaults.adapter = (config: InternalAxiosRequestConfig) =>
    Promise.reject(
      new AxiosError("fail", "ERR", config, undefined, {
        status,
        statusText: "",
        headers: {},
        config,
        data: { detail },
      }),
    );
}

const realLocation = window.location;

function stubLocation(pathname: string) {
  Object.defineProperty(window, "location", {
    value: { pathname, href: pathname },
    writable: true,
    configurable: true,
  });
}

describe("api response interceptor (MFA)", () => {
  afterEach(() => {
    Object.defineProperty(window, "location", { value: realLocation, configurable: true });
    vi.restoreAllMocks();
  });

  it("sends an unenrolled admin to MFA setup on 403 mfa_enrollment_required", async () => {
    stubLocation("/admin/companies");
    failWith(403, "mfa_enrollment_required");

    await expect(api.get("/api/admin/companies")).rejects.toBeInstanceOf(AxiosError);
    expect(window.location.href).toBe(MFA_SETUP_PATH);
  });

  it("does not redirect when already on the setup page", async () => {
    stubLocation(MFA_SETUP_PATH);
    failWith(403, "mfa_enrollment_required");

    await expect(api.get("/api/admin/x")).rejects.toBeInstanceOf(AxiosError);
    expect(window.location.href).toBe(MFA_SETUP_PATH);
  });

  it.each(["invalid_mfa_code", "mfa_challenge_expired"])(
    "does not try a token refresh for a 401 %s",
    async (detail) => {
      stubLocation("/login");
      const refresh = vi.spyOn(axios, "post");
      failWith(401, detail);

      await expect(api.post("/auth/mfa/verify", {})).rejects.toBeInstanceOf(AxiosError);
      expect(refresh).not.toHaveBeenCalled();
    },
  );
});

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import "@/i18n";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import MfaSetupPage from "@/pages/admin/MfaSetupPage";

const { mockStart, mockConfirm } = vi.hoisted(() => ({
  mockStart: vi.fn(),
  mockConfirm: vi.fn(),
}));
vi.mock("@/services/auth", () => ({
  startMfaEnrolment: mockStart,
  confirmMfaEnrolment: mockConfirm,
}));
// jsdom has no canvas: the QR image itself is not under test.
vi.mock("qrcode", () => ({
  default: { toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,AAAA") },
}));

const CODES = ["aaaaa-bbbbb", "ccccc-ddddd"];

function apiError(status: number, detail: string): AxiosError {
  return new AxiosError("fail", "ERR", undefined, undefined, {
    status,
    statusText: "",
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { detail },
  });
}

async function confirmWith(value: string) {
  await screen.findByTestId("mfa-secret");
  fireEvent.change(screen.getByRole("textbox"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: /הפעלת אימות/ }));
}

function renderPage() {
  const refreshUserFromToken = vi.fn();
  const logout = vi.fn();
  const ctx = {
    user: null,
    isAuthenticated: true,
    isInitializing: false,
    isLoggingOut: false,
    login: vi.fn(),
    completeMfaLogin: vi.fn(),
    refreshUserFromToken,
    logout,
  } as AuthContextType;
  render(
    <MemoryRouter>
      <AuthContext.Provider value={ctx}>
        <MfaSetupPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  return { refreshUserFromToken, logout };
}

describe("MfaSetupPage", () => {
  beforeEach(() => {
    mockStart.mockReset().mockResolvedValue({
      secret: "JBSWY3DPEHPK3PXP",
      otpauth_uri: "otpauth://totp/x?secret=JBSWY3DPEHPK3PXP",
    });
    mockConfirm.mockReset().mockResolvedValue({
      recovery_codes: CODES,
      access_token: "t",
      token_type: "bearer",
    });
  });

  it("shows the manual key, confirms the code, then shows recovery codes once", async () => {
    const { refreshUserFromToken } = renderPage();

    // Grouped in fours for typing by hand.
    expect(await screen.findByTestId("mfa-secret")).toHaveTextContent(
      "JBSW Y3DP EHPK 3PXP",
    );
    expect(mockStart).toHaveBeenCalledTimes(1);

    await confirmWith("123 456");

    const list = await screen.findByTestId("recovery-codes");
    expect(list).toHaveTextContent("aaaaa-bbbbb");
    expect(mockConfirm).toHaveBeenCalledWith("123456");
    // MFA is on at once: leaving now can't bounce back here and lose the codes.
    expect(refreshUserFromToken).toHaveBeenCalledTimes(1);

    // Continue stays disabled until the codes are acknowledged as saved.
    const proceed = screen.getByRole("button", { name: /המשך/ });
    expect(proceed).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(proceed).toBeEnabled();
  });

  it("warns before the tab closes until the codes are saved", async () => {
    renderPage();
    await confirmWith("123456");
    await screen.findByTestId("recovery-codes");

    const unsaved = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(unsaved);
    expect(unsaved.defaultPrevented).toBe(true);

    fireEvent.click(screen.getByRole("checkbox"));
    const saved = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(saved);
    expect(saved.defaultPrevented).toBe(false);
  });

  it("offers logout while setting up, but not while the codes are unsaved", async () => {
    const { logout } = renderPage();
    await screen.findByTestId("mfa-secret");

    fireEvent.click(screen.getByRole("button", { name: "התנתקות" }));
    expect(logout).toHaveBeenCalled();

    await confirmWith("123456");
    await screen.findByTestId("recovery-codes");
    expect(screen.queryByRole("button", { name: "התנתקות" })).toBeNull();
  });

  it("holds Back on the page until the codes are saved", async () => {
    renderPage();
    await confirmWith("123456");
    await screen.findByTestId("recovery-codes");

    act(() => {
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(screen.getByTestId("recovery-codes")).toBeDefined();
    expect((await screen.findByRole("alert")).textContent).toMatch(/עוד לא סימנתם/);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps the scan step with an error for a wrong code", async () => {
    mockConfirm.mockRejectedValue(apiError(401, "invalid_mfa_code"));
    renderPage();

    await confirmWith("000000");

    expect((await screen.findByRole("alert")).textContent).toMatch(/הקוד שגוי/);
    expect(screen.queryByTestId("recovery-codes")).toBeNull();
  });

  it("does not blame the code for other failures", async () => {
    mockConfirm.mockRejectedValue(new Error("network"));
    renderPage();

    await confirmWith("000000");

    expect((await screen.findByRole("alert")).textContent).toMatch(/לא הצלחנו להפעיל/);
  });

  it("explains the hourly limit on a 429", async () => {
    mockConfirm.mockRejectedValue(apiError(429, "rate_limited"));
    renderPage();

    await confirmWith("000000");

    expect(await screen.findByText(/יותר מדי ניסיונות/)).toBeDefined();
  });

  it("shows an error when enrolment can't start", async () => {
    mockStart.mockRejectedValue(new Error("down"));
    renderPage();
    await waitFor(() => expect(screen.getByText(/לא הצלחנו להתחיל/)).toBeDefined());
  });
});

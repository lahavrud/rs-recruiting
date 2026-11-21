import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function renderPage() {
  const refreshUserFromToken = vi.fn();
  const ctx = {
    user: null,
    isAuthenticated: true,
    isInitializing: false,
    isLoggingOut: false,
    login: vi.fn(),
    completeMfaLogin: vi.fn(),
    refreshUserFromToken,
    logout: vi.fn(),
  } as AuthContextType;
  render(
    <MemoryRouter>
      <AuthContext.Provider value={ctx}>
        <MfaSetupPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
  return { refreshUserFromToken };
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

    expect(await screen.findByTestId("mfa-secret")).toHaveTextContent("JBSWY3DPEHPK3PXP");
    expect(mockStart).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: /הפעלת אימות/ }));

    const list = await screen.findByTestId("recovery-codes");
    expect(list).toHaveTextContent("aaaaa-bbbbb");
    expect(mockConfirm).toHaveBeenCalledWith("123456");

    // Continue stays disabled until the codes are acknowledged as saved.
    const proceed = screen.getByRole("button", { name: /המשך/ });
    expect(proceed).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(proceed);
    expect(refreshUserFromToken).toHaveBeenCalled();
  });

  it("keeps the scan step with an error for a wrong code", async () => {
    mockConfirm.mockRejectedValue(new Error("nope"));
    renderPage();
    await screen.findByTestId("mfa-secret");

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: /הפעלת אימות/ }));

    expect(await screen.findByText(/הקוד שגוי/)).toBeDefined();
    expect(screen.queryByTestId("recovery-codes")).toBeNull();
  });

  it("shows an error when enrolment can't start", async () => {
    mockStart.mockRejectedValue(new Error("down"));
    renderPage();
    await waitFor(() => expect(screen.getByText(/לא הצלחנו להתחיל/)).toBeDefined());
  });
});

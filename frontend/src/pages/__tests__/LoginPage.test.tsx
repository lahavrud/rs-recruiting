import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import "@/i18n";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import LoginPage from "@/pages/LoginPage";

function apiError(
  status: number,
  detail: string,
  headers: Record<string, string> = {},
): AxiosError {
  return new AxiosError("fail", "ERR", undefined, undefined, {
    status,
    statusText: "",
    headers,
    config: { headers: new AxiosHeaders() },
    data: { detail },
  });
}

function renderLogin(overrides: Partial<AuthContextType>) {
  const ctx = {
    user: null,
    isAuthenticated: false,
    isInitializing: false,
    isLoggingOut: false,
    login: vi.fn(),
    completeMfaLogin: vi.fn(),
    refreshUserFromToken: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  } as AuthContextType;
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthContext.Provider value={ctx}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>dashboard</p>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

function submitPassword() {
  fireEvent.change(screen.getByLabelText("כתובת אימייל"), {
    target: { value: "admin@example.com" },
  });
  fireEvent.change(screen.getByLabelText("סיסמה"), {
    target: { value: "CorrectHorse1!" },
  });
  fireEvent.submit(screen.getByLabelText("סיסמה").closest("form")!);
}

function submitCode() {
  fireEvent.change(screen.getByLabelText("קוד אימות"), { target: { value: "123456" } });
  fireEvent.submit(screen.getByLabelText("קוד אימות").closest("form")!);
}

describe("LoginPage with MFA", () => {
  it("asks for the code after the password, without reset or signup links", async () => {
    const completeMfaLogin = vi.fn().mockResolvedValue(undefined);
    renderLogin({ login: vi.fn().mockResolvedValue({ mfaToken: "challenge" }), completeMfaLogin });

    expect(screen.getByText("שכחת סיסמה?")).toBeDefined();
    submitPassword();

    expect(await screen.findByLabelText("קוד אימות")).toBeDefined();
    expect(screen.queryByText("שכחת סיסמה?")).toBeNull();
    expect(screen.getByText("admin@example.com")).toBeDefined();

    submitCode();
    expect(await screen.findByText("dashboard")).toBeDefined();
    expect(completeMfaLogin).toHaveBeenCalledWith("challenge", { code: "123456" });
  });

  it("returns to the password step with the lock time", async () => {
    renderLogin({
      login: vi.fn().mockResolvedValue({ mfaToken: "challenge" }),
      completeMfaLogin: vi
        .fn()
        .mockRejectedValue(apiError(429, "mfa_locked", { "retry-after": "600" })),
    });
    submitPassword();
    await screen.findByLabelText("קוד אימות");

    submitCode();

    expect(await screen.findByText(/נעולה ל-10 דקות/)).toBeDefined();
    expect(screen.getByLabelText("סיסמה")).toHaveValue("");
    expect(screen.getByText("שכחת סיסמה?")).toBeDefined();
  });

  it("returns to the password step when the challenge expired", async () => {
    renderLogin({
      login: vi.fn().mockResolvedValue({ mfaToken: "challenge" }),
      completeMfaLogin: vi.fn().mockRejectedValue(apiError(401, "mfa_challenge_expired")),
    });
    submitPassword();
    await screen.findByLabelText("קוד אימות");

    submitCode();

    expect(await screen.findByText(/תם הזמן לאימות/)).toBeDefined();
  });

  it("gives the wait time for a throttled password login", async () => {
    renderLogin({
      login: vi.fn().mockRejectedValue(apiError(429, "account_locked", { "retry-after": "120" })),
    });

    submitPassword();

    await waitFor(() => expect(screen.getByText(/בעוד שתי דקות/)).toBeDefined());
  });
});

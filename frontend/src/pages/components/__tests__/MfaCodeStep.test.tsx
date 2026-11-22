import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { vi } from "vitest";

import "@/i18n";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import MfaCodeStep from "@/pages/components/MfaCodeStep";

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

function renderStep(completeMfaLogin: AuthContextType["completeMfaLogin"]) {
  const onDone = vi.fn();
  const onRestart = vi.fn();
  const ctx = {
    user: null,
    isAuthenticated: false,
    isInitializing: false,
    isLoggingOut: false,
    login: vi.fn(),
    completeMfaLogin,
    refreshUserFromToken: vi.fn(),
    logout: vi.fn(),
  } as AuthContextType;
  render(
    <AuthContext.Provider value={ctx}>
      <MfaCodeStep
        mfaToken="challenge"
        email="admin@example.com"
        onDone={onDone}
        onRestart={onRestart}
      />
    </AuthContext.Provider>,
  );
  return { onDone, onRestart };
}

function submit(value: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value } });
  fireEvent.submit(screen.getByRole("textbox").closest("form")!);
}

describe("MfaCodeStep", () => {
  it("sends the code and finishes the login", async () => {
    const complete = vi.fn().mockResolvedValue(undefined);
    const { onDone } = renderStep(complete);

    submit("123456");

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(complete).toHaveBeenCalledWith("challenge", { code: "123456" });
  });

  it("keeps all six digits of a code pasted with a space", () => {
    renderStep(vi.fn());

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123 456" } });

    expect(screen.getByRole("textbox")).toHaveValue("123456");
  });

  it("enables the submit button only for a full code", () => {
    renderStep(vi.fn());
    const button = screen.getByRole("button", { name: /אימות והתחברות/ });

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "12345" } });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123456" } });
    expect(button).toBeEnabled();
  });

  it("shows which account is signing in", () => {
    renderStep(vi.fn());
    expect(screen.getByText("admin@example.com")).toBeDefined();
  });

  it("sends a recovery code after switching modes", async () => {
    const complete = vi.fn().mockResolvedValue(undefined);
    renderStep(complete);

    fireEvent.click(screen.getByRole("button", { name: /קוד שחזור/ }));
    submit("abcde-fghjk");

    await waitFor(() =>
      expect(complete).toHaveBeenCalledWith("challenge", {
        recovery_code: "abcde-fghjk",
      }),
    );
  });

  it("shows a Hebrew error for a wrong code and stays on the step", async () => {
    const complete = vi.fn().mockRejectedValue(apiError(401, "invalid_mfa_code"));
    const { onDone, onRestart } = renderStep(complete);

    submit("000000");

    expect((await screen.findByRole("alert")).textContent).toMatch(/הקוד שגוי/);
    expect(onDone).not.toHaveBeenCalled();
    expect(onRestart).not.toHaveBeenCalled();
  });

  it("treats a malformed code (422) as a wrong code", async () => {
    const complete = vi.fn().mockRejectedValue(apiError(422, "x"));
    renderStep(complete);

    submit("123456");

    expect(await screen.findByText(/הקוד שגוי/)).toBeDefined();
  });

  it("goes back to the password step when the challenge expired", async () => {
    const complete = vi.fn().mockRejectedValue(apiError(401, "mfa_challenge_expired"));
    const { onRestart } = renderStep(complete);

    submit("123456");

    await waitFor(() => expect(onRestart).toHaveBeenCalledWith("expired"));
  });

  it("sends a locked account back to the password step with the time left", async () => {
    const complete = vi
      .fn()
      .mockRejectedValue(apiError(429, "mfa_locked", { "retry-after": "300" }));
    const { onRestart } = renderStep(complete);

    submit("123456");

    await waitFor(() => expect(onRestart).toHaveBeenCalledWith("locked", 5));
  });

  it("shows the generic throttle message for a plain 429", async () => {
    const complete = vi.fn().mockRejectedValue(apiError(429, "account_locked"));
    const { onRestart } = renderStep(complete);

    submit("123456");

    expect(await screen.findByText(/יותר מדי ניסיונות התחברות/)).toBeDefined();
    expect(onRestart).not.toHaveBeenCalled();
  });

  it("lets the user go back to the password step", () => {
    const { onRestart } = renderStep(vi.fn());

    fireEvent.click(screen.getByRole("button", { name: /חזרה להתחברות/ }));

    expect(onRestart).toHaveBeenCalledWith("cancel");
  });
});

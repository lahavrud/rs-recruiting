import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { vi } from "vitest";

import "@/i18n";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import MfaCodeStep from "@/pages/components/MfaCodeStep";

function apiError(status: number, detail: string): AxiosError {
  return new AxiosError("fail", "ERR", undefined, undefined, {
    status,
    statusText: "",
    headers: {},
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
      <MfaCodeStep mfaToken="challenge" onDone={onDone} onRestart={onRestart} />
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

    submit("123 456");

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(complete).toHaveBeenCalledWith("challenge", { code: "123456" });
  });

  it("sends a recovery code after switching modes", async () => {
    const complete = vi.fn().mockResolvedValue(undefined);
    renderStep(complete);

    fireEvent.click(screen.getByRole("button", { name: /קוד שחזור/ }));
    submit("abcde-fghjk");

    await waitFor(() =>
      expect(complete).toHaveBeenCalledWith("challenge", { recovery_code: "abcde-fghjk" }),
    );
  });

  it("shows a Hebrew error for a wrong code and stays on the step", async () => {
    const complete = vi.fn().mockRejectedValue(apiError(401, "invalid_mfa_code"));
    const { onDone, onRestart } = renderStep(complete);

    submit("000000");

    expect(await screen.findByText(/הקוד שגוי/)).toBeDefined();
    expect(onDone).not.toHaveBeenCalled();
    expect(onRestart).not.toHaveBeenCalled();
  });

  it("goes back to the password step when the challenge expired", async () => {
    const complete = vi.fn().mockRejectedValue(apiError(401, "mfa_challenge_expired"));
    const { onRestart } = renderStep(complete);

    submit("123456");

    await waitFor(() => expect(onRestart).toHaveBeenCalledWith("expired"));
  });
});

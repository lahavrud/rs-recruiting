import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { vi } from "vitest";

import "@/i18n";
import MfaRecoveryCard from "@/pages/admin/components/MfaRecoveryCard";

const { mockStatus, mockRegenerate } = vi.hoisted(() => ({
  mockStatus: vi.fn(),
  mockRegenerate: vi.fn(),
}));
vi.mock("@/services/auth", () => ({
  getMfaStatus: mockStatus,
  regenerateRecoveryCodes: mockRegenerate,
}));

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

function submit(value: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value } });
  fireEvent.submit(screen.getByRole("textbox").closest("form")!);
}

describe("MfaRecoveryCard", () => {
  beforeEach(() => {
    mockStatus.mockReset();
    mockRegenerate.mockReset();
  });

  it("shows how many codes are left", async () => {
    mockStatus.mockResolvedValue({ enabled: true, recovery_codes_remaining: 8 });
    render(<MfaRecoveryCard />);

    const line = await screen.findByTestId("recovery-remaining");
    expect(line.textContent).toContain("8");
    expect(line.textContent).not.toContain("מעט");
  });

  it("warns when few codes are left", async () => {
    mockStatus.mockResolvedValue({ enabled: true, recovery_codes_remaining: 2 });
    render(<MfaRecoveryCard />);

    expect((await screen.findByTestId("recovery-remaining")).textContent).toContain(
      "מעט",
    );
  });

  it("shows the new codes once generated", async () => {
    mockStatus.mockResolvedValue({ enabled: true, recovery_codes_remaining: 1 });
    mockRegenerate.mockResolvedValue({ recovery_codes: ["aaaaa-bbbbb"] });
    render(<MfaRecoveryCard />);

    submit("123 456");

    await waitFor(() => expect(mockRegenerate).toHaveBeenCalledWith("123456"));
    expect(await screen.findByText("aaaaa-bbbbb")).toBeDefined();

    // "Saved" hides them and brings the form back.
    fireEvent.click(screen.getByRole("button", { name: /שמרתי/ }));
    expect(screen.queryByText("aaaaa-bbbbb")).toBeNull();
    expect(screen.getByRole("textbox")).toBeDefined();
  });

  it("says when the code is wrong", async () => {
    mockStatus.mockResolvedValue({ enabled: true, recovery_codes_remaining: 5 });
    mockRegenerate.mockRejectedValue(apiError(401, "invalid_mfa_code"));
    render(<MfaRecoveryCard />);

    submit("000000");

    expect((await screen.findByRole("alert")).textContent).toMatch(/הקוד שגוי/);
  });

  it("gives the lock time when the account is locked", async () => {
    mockStatus.mockResolvedValue({ enabled: true, recovery_codes_remaining: 5 });
    mockRegenerate.mockRejectedValue(
      apiError(429, "mfa_locked", { "retry-after": "600" }),
    );
    render(<MfaRecoveryCard />);

    submit("000000");

    expect((await screen.findByRole("alert")).textContent).toContain("10 דקות");
  });

  it("maps a plain rate limit to a Hebrew message", async () => {
    mockStatus.mockResolvedValue({ enabled: true, recovery_codes_remaining: 5 });
    mockRegenerate.mockRejectedValue(apiError(429, "x"));
    render(<MfaRecoveryCard />);

    submit("000000");

    expect((await screen.findByRole("alert")).textContent).toMatch(/יותר מדי ניסיונות/);
  });
});

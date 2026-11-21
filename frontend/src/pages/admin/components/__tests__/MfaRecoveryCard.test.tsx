import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "123456" } });
    fireEvent.submit(screen.getByRole("textbox").closest("form")!);

    await waitFor(() => expect(mockRegenerate).toHaveBeenCalledWith("123456"));
    expect(await screen.findByText("aaaaa-bbbbb")).toBeDefined();
  });
});

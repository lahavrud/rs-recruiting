import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import "@/i18n";
import RecoveryCodesList from "@/pages/admin/components/RecoveryCodesList";

const CODES = ["aaaaa-bbbbb", "ccccc-ddddd"];

function mockClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
}

describe("RecoveryCodesList", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("lists every code left-to-right", () => {
    render(<RecoveryCodesList codes={CODES} />);
    const list = screen.getByTestId("recovery-codes");
    expect(list.getAttribute("dir")).toBe("ltr");
    expect(list.textContent).toContain("ccccc-ddddd");
  });

  it("copies all codes and confirms, then resets", async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    mockClipboard(writeText);
    render(<RecoveryCodesList codes={CODES} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "העתקה" }));
    });

    expect(writeText).toHaveBeenCalledWith("aaaaa-bbbbb\nccccc-ddddd");
    expect(screen.getByRole("button", { name: "הועתק" })).toBeDefined();
    act(() => vi.runAllTimers());
    expect(screen.getByRole("button", { name: "העתקה" })).toBeDefined();
  });

  it("says so when the browser blocks the clipboard", async () => {
    mockClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<RecoveryCodesList codes={CODES} />);

    fireEvent.click(screen.getByRole("button", { name: "העתקה" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/נחסמה/);
  });

  it("downloads the codes as a text file", () => {
    vi.useFakeTimers();
    const createUrl = vi.fn().mockReturnValue("blob:x");
    const revokeUrl = vi.fn();
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: revokeUrl });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<RecoveryCodesList codes={CODES} />);

    fireEvent.click(screen.getByRole("button", { name: /הורדה/ }));

    expect(click).toHaveBeenCalled();
    expect(revokeUrl).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revokeUrl).toHaveBeenCalledWith("blob:x");
  });
});

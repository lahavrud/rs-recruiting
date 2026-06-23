import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildResumeDownloadName,
  downloadOrShareBlob,
  isInlinePreviewable,
  isIOS,
} from "@/utils/resume";

describe("buildResumeDownloadName", () => {
  it("maps a known PDF MIME to the canonical .pdf extension", () => {
    expect(
      buildResumeDownloadName("Michal Cohen", "abc123", "application/pdf"),
    ).toBe("Michal-Cohen-resume.pdf");
  });

  it("maps a known DOCX MIME to the canonical .docx extension", () => {
    expect(
      buildResumeDownloadName(
        "David Mizrahi",
        "xyz",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ),
    ).toBe("David-Mizrahi-resume.docx");
  });

  it("falls back to the file-key extension when the MIME is unknown", () => {
    expect(
      buildResumeDownloadName(
        "Yael Levi",
        "fc2f8b8a.docx",
        "application/octet-stream",
      ),
    ).toBe("Yael-Levi-resume.docx");
  });

  it("falls back to .bin when neither MIME nor file-key extension is usable", () => {
    expect(
      buildResumeDownloadName("Noa", "fc2f8b8a-no-ext", "application/octet-stream"),
    ).toBe("Noa-resume.bin");
  });

  it("rejects suspicious file-key extensions (forces .bin fallback)", () => {
    // A "file key" ending in a long token that's not a real extension —
    // safe fallback prevents `something.exe` shenanigans landing as the ext.
    expect(
      buildResumeDownloadName(
        "Test",
        "abc.thisisnotanextension",
        "application/octet-stream",
      ),
    ).toBe("Test-resume.bin");
  });

  it("collapses whitespace in the candidate name to single hyphens", () => {
    expect(
      buildResumeDownloadName(
        "  Two   Spaces  Around  ",
        "x.pdf",
        "application/pdf",
      ),
    ).toBe("Two-Spaces-Around-resume.pdf");
  });

  it("handles Hebrew names without mangling characters", () => {
    expect(
      buildResumeDownloadName("יואב כהן", "x.pdf", "application/pdf"),
    ).toBe("יואב-כהן-resume.pdf");
  });
});

describe("isInlinePreviewable", () => {
  it("returns true for PDF MIME", () => {
    expect(isInlinePreviewable("application/pdf", "anything")).toBe(true);
  });

  it("returns true for .pdf file-key when MIME is generic", () => {
    expect(isInlinePreviewable("application/octet-stream", "abc.pdf")).toBe(true);
  });

  it("is case-insensitive on the file-key extension check", () => {
    expect(isInlinePreviewable("application/octet-stream", "abc.PDF")).toBe(true);
  });

  it("returns false for DOCX MIME", () => {
    expect(
      isInlinePreviewable(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "x.docx",
      ),
    ).toBe(false);
  });

  it("returns false for legacy DOC MIME", () => {
    expect(isInlinePreviewable("application/msword", "x.doc")).toBe(false);
  });

  it("returns false for unknown MIME without a .pdf hint", () => {
    expect(isInlinePreviewable("application/octet-stream", "x.xyz")).toBe(false);
  });
});

describe("isIOS", () => {
  const originalNavigator = global.navigator;

  afterEach(() => {
    Object.defineProperty(global, "navigator", {
      value: originalNavigator,
      configurable: true,
      writable: true,
    });
  });

  function setNavigator(props: Partial<Navigator>) {
    Object.defineProperty(global, "navigator", {
      value: { ...originalNavigator, ...props },
      configurable: true,
      writable: true,
    });
  }

  it("detects iPhone", () => {
    setNavigator({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)" });
    expect(isIOS()).toBe(true);
  });

  it("detects iPad on legacy user agents", () => {
    setNavigator({ userAgent: "Mozilla/5.0 (iPad; CPU OS 17_0)" });
    expect(isIOS()).toBe(true);
  });

  it("detects iPadOS 13+ that masquerades as macOS with touch support", () => {
    setNavigator({
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      platform: "MacIntel",
      maxTouchPoints: 5,
    });
    expect(isIOS()).toBe(true);
  });

  it("returns false on plain desktop macOS (no touch)", () => {
    setNavigator({
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      platform: "MacIntel",
      maxTouchPoints: 0,
    });
    expect(isIOS()).toBe(false);
  });

  it("returns false on Android", () => {
    setNavigator({
      userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8)",
      platform: "Linux armv8l",
      maxTouchPoints: 5,
    });
    expect(isIOS()).toBe(false);
  });
});

describe("downloadOrShareBlob (non-iOS path)", () => {
  const originalNavigator = global.navigator;
  let appendChildSpy: ReturnType<typeof vi.spyOn>;
  let removeChildSpy: ReturnType<typeof vi.spyOn>;
  let clickSpy: ReturnType<typeof vi.fn>;
  let revokeSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Force non-iOS (so the function takes the <a download> path)
    Object.defineProperty(global, "navigator", {
      value: { ...originalNavigator, userAgent: "Mozilla/5.0 (X11; Linux)" },
      configurable: true,
      writable: true,
    });
    appendChildSpy = vi
      .spyOn(document.body, "appendChild")
      .mockImplementation((node: Node) => node);
    removeChildSpy = vi
      .spyOn(document.body, "removeChild")
      .mockImplementation((node: Node) => node);
    clickSpy = vi.fn();
    revokeSpy = vi.fn();
    URL.createObjectURL = vi.fn(() => "blob:fake-url");
    URL.revokeObjectURL = revokeSpy;
    // Intercept createElement('a') so we can assert on the synthetic link
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation(
      (tag: string, opts?: ElementCreationOptions) => {
        const el = originalCreateElement(tag, opts);
        if (tag === "a") {
          el.click = clickSpy;
        }
        return el;
      },
    );
  });

  afterEach(() => {
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
    vi.restoreAllMocks();
    Object.defineProperty(global, "navigator", {
      value: originalNavigator,
      configurable: true,
      writable: true,
    });
  });

  it("creates an <a download>, clicks it, and reports success", async () => {
    const blob = new Blob(["hello"], { type: "application/pdf" });
    const result = await downloadOrShareBlob(blob, "test.pdf");
    expect(result).toBe(true);
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(appendChildSpy).toHaveBeenCalledOnce();
    expect(removeChildSpy).toHaveBeenCalledOnce();
  });
});

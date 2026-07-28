/**
 * The push banner's error handling discriminates four outcomes, three of them
 * added alongside the job-close cascade fixes. Two distinct 409s reach it — the
 * job closed under an already-loaded feed, and the pair has already applied —
 * so branching on the bare status is not enough; it reads the error code.
 *
 * Every outcome the job itself can no longer satisfy is terminal for the
 * banner: retrying cannot succeed, so the ?job= param is cleared rather than
 * left inviting another attempt. Only a genuinely unknown failure keeps it.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n"; // initialize i18next so t() resolves to real Hebrew strings
import CandidateMatchesPanel from "@/pages/admin/components/CandidateMatchesPanel";
import type { CandidateJobMatchRead } from "@/types/candidates";

// ── Service + toast mocks ─────────────────────────────────────────────────

const { mockGetMatches, mockPushMatch, mockDismissMatch, mockToast } = vi.hoisted(() => ({
  mockGetMatches: vi.fn(),
  mockPushMatch: vi.fn(),
  mockDismissMatch: vi.fn(),
  mockToast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

vi.mock("@/services/adminCandidates", () => ({
  getCandidateJobMatches: mockGetMatches,
}));
vi.mock("@/services/adminMatches", () => ({
  pushMatch: mockPushMatch,
  dismissMatch: mockDismissMatch,
}));
vi.mock("@/hooks/useToast", () => ({
  useToast: () => mockToast,
}));

// ── Fixtures ──────────────────────────────────────────────────────────────

const MATCH: CandidateJobMatchRead = {
  job: {
    id: 42,
    title: "מנהל מוצר",
    company_name: "אלפא",
    location: "תל אביב",
  },
  score: 0.91,
} as unknown as CandidateJobMatchRead;

/** An axios-shaped rejection, which is what the handler actually inspects. */
function httpError(status: number, detail?: string) {
  return { response: { status, data: detail === undefined ? {} : { detail } } };
}

async function renderPanelAndPush() {
  mockGetMatches.mockResolvedValue([MATCH]);
  render(
    <MemoryRouter initialEntries={["/admin/candidates/1?job=42"]}>
      <CandidateMatchesPanel candidateId={1} />
    </MemoryRouter>,
  );
  const button = await screen.findByRole("button", { name: "קדם מועמדות" });
  fireEvent.click(button);
}

describe("CandidateMatchesPanel push error handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reports the job closing under the feed, and stops offering the push", async () => {
    mockPushMatch.mockRejectedValue(httpError(409, "job_not_published"));
    await renderPanelAndPush();

    await waitFor(() => expect(mockToast.info).toHaveBeenCalled());
    expect(mockToast.info.mock.calls[0][0]).toContain("נסגרה");
    expect(mockToast.error).not.toHaveBeenCalled();
    // Banner dismissed — the job can never accept this push.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "קדם מועמדות" })).not.toBeInTheDocument(),
    );
  });

  it("reports a deleted job distinctly, rather than as a generic failure", async () => {
    mockPushMatch.mockRejectedValue(httpError(404, "job_not_found"));
    await renderPanelAndPush();

    await waitFor(() => expect(mockToast.info).toHaveBeenCalled());
    // Previously fell through to the generic error branch, which also left the
    // banner open inviting a retry that could never succeed.
    expect(mockToast.error).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "קדם מועמדות" })).not.toBeInTheDocument(),
    );
  });

  it("still reports an existing application for a plain 409", async () => {
    mockPushMatch.mockRejectedValue(httpError(409, "already_applied"));
    await renderPanelAndPush();

    await waitFor(() => expect(mockToast.info).toHaveBeenCalled());
    expect(mockToast.info.mock.calls[0][0]).toContain("כבר");
    expect(mockToast.error).not.toHaveBeenCalled();
  });

  it("keeps the banner open for an unknown failure, which may be retryable", async () => {
    mockPushMatch.mockRejectedValue(httpError(500, undefined));
    await renderPanelAndPush();

    await waitFor(() => expect(mockToast.error).toHaveBeenCalled());
    expect(mockToast.info).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "קדם מועמדות" })).toBeInTheDocument();
  });

  it("confirms success and clears the banner", async () => {
    mockPushMatch.mockResolvedValue({ id: 7 });
    await renderPanelAndPush();

    await waitFor(() => expect(mockToast.success).toHaveBeenCalled());
    expect(mockToast.error).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "קדם מועמדות" })).not.toBeInTheDocument(),
    );
  });
});

/**
 * Guards the #1022 fix: MobileJobCard renders one card per job in the admin
 * jobs list, and its JobDetailBody child fires two data fetches on mount
 * (applications + candidate-matches). Mounting the body eagerly fired both for
 * every job on page load; the card must defer mounting the body — and thus the
 * fetches — until it is first expanded.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n"; // initialize i18next so t() resolves to real Hebrew strings
import { MobileJobCard } from "@/pages/admin/components/JobViewBody";
import type { JobRead } from "@/types/jobs";

// ── Service mocks ─────────────────────────────────────────────────────────

const { mockGetApplications, mockGetJobCandidateMatches } = vi.hoisted(() => ({
  mockGetApplications: vi.fn(),
  mockGetJobCandidateMatches: vi.fn(),
}));

vi.mock("@/services/adminApplications", () => ({
  getApplications: mockGetApplications,
}));
vi.mock("@/services/adminJobs", () => ({
  getJobCandidateMatches: mockGetJobCandidateMatches,
}));

// ── Fixtures ──────────────────────────────────────────────────────────────

const JOB: JobRead = {
  id: 42,
  company_id: 7,
  title: "מנהל מוצר",
  short_description: "תיאור קצר",
  description: "תיאור מלא",
  requirements: [],
  tags: [],
  is_featured: false,
  location: "תל אביב",
  salary_min: 10000,
  salary_max: 20000,
  status: "PUBLISHED" as never,
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

const STATUS_LABELS = { PUBLISHED: "מפורסמת" };
const STATUS_COLORS = { PUBLISHED: "text-success" };

function renderCard() {
  return render(
    <MemoryRouter>
      <MobileJobCard
        job={JOB}
        statusLabels={STATUS_LABELS}
        statusColors={STATUS_COLORS}
        actions={null}
      />
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockGetApplications.mockReset().mockResolvedValue({ items: [], next_cursor: null });
  mockGetJobCandidateMatches.mockReset().mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MobileJobCard", () => {
  it("fires no fetches while collapsed on mount", () => {
    renderCard();
    expect(mockGetApplications).not.toHaveBeenCalled();
    expect(mockGetJobCandidateMatches).not.toHaveBeenCalled();
  });

  it("keeps nothing but the toggle focusable until first expanded", () => {
    renderCard();
    // The detail body and its 'close' button are gated on first-open, so a
    // never-opened card leaves only the expand toggle in the tab order.
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("fetches applications + candidate-matches only once the card is expanded", async () => {
    renderCard();

    fireEvent.click(screen.getByRole("button", { expanded: false }));

    await waitFor(() => expect(mockGetApplications).toHaveBeenCalledTimes(1));
    expect(mockGetApplications).toHaveBeenCalledWith(
      { job_id: JOB.id, sort: "score" },
      expect.any(AbortSignal),
    );
    expect(mockGetJobCandidateMatches).toHaveBeenCalledTimes(1);
    expect(mockGetJobCandidateMatches).toHaveBeenCalledWith(
      JOB.id,
      expect.any(AbortSignal),
    );
  });

  it("does not refetch when the card is collapsed and re-expanded", async () => {
    renderCard();

    // Capture the card's own toggle before the body mounts — afterwards the
    // expanded detail contains CollapsibleSection headers that also carry
    // aria-expanded, so query it now while it's the only aria-expanded button.
    const toggle = screen.getByRole("button", { expanded: false });

    // Expand → fetch once.
    fireEvent.click(toggle);
    await waitFor(() => expect(mockGetApplications).toHaveBeenCalledTimes(1));

    // Collapse, then re-expand — the body stays mounted, so no new fetch.
    fireEvent.click(toggle);
    fireEvent.click(toggle);

    expect(mockGetApplications).toHaveBeenCalledTimes(1);
    expect(mockGetJobCandidateMatches).toHaveBeenCalledTimes(1);
  });
});

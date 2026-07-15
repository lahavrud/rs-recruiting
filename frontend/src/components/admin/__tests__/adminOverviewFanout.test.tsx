/**
 * Integration guard for #1051: several admin surfaces consume the overview
 * payload, and mounting them together must produce ONE `GET /api/admin/overview`
 * request — not one per component — now that they share `useAdminOverview`.
 */
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import AdminInbox from "@/components/admin/AdminInbox";
import AdminRecentFeed from "@/components/admin/AdminRecentFeed";
import { resetAdminOverviewShared } from "@/hooks/useAdminOverview";
import type { AdminOverviewRead } from "@/services/adminOverview";

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));
vi.mock("@/services/api", () => ({ default: { get: mockGet } }));

const PAYLOAD: AdminOverviewRead = {
  inbox: {
    pending_invites: 1,
    pending_companies: 2,
    pending_jobs: 3,
    new_applications: 4,
    oldest_pending_company_days: null,
    oldest_pending_job_days: null,
    oldest_new_application_days: null,
  },
  stats: {
    active_companies: 5,
    published_jobs: 6,
    total_candidates: 7,
    application_status_counts: {},
    top_jobs: [],
  },
  pulse: {
    new_candidates_7d: 0,
    new_applications_7d: 0,
    recent_items: [],
    trend_30d: [],
  },
};

beforeEach(() => {
  resetAdminOverviewShared();
  mockGet.mockReset().mockResolvedValue({ data: PAYLOAD });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("admin overview fan-out", () => {
  it("fires a single /api/admin/overview request for co-mounted consumers", async () => {
    render(
      <MemoryRouter>
        <AdminInbox />
        <AdminRecentFeed />
      </MemoryRouter>,
    );

    await waitFor(() => expect(mockGet).toHaveBeenCalled());
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith("/api/admin/overview", expect.anything());
  });
});

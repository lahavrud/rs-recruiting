/**
 * The pending-work cards must land on the review queue tab that holds that
 * work. They once linked to `/admin/applications?status=NEW` — a status the
 * applications page doesn't recognise, so it silently showed every application.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminInbox from "@/components/admin/AdminInbox";
import { resetAdminOverviewShared } from "@/hooks/useAdminOverview";
import i18n from "@/i18n";
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

function cardHref(labelKey: string): string | null {
  const label = i18n.t(labelKey);
  return screen.getByText(label).closest("a")?.getAttribute("href") ?? null;
}

describe("AdminInbox", () => {
  it("links each pending-work card to its review queue tab", async () => {
    render(
      <MemoryRouter>
        <AdminInbox />
      </MemoryRouter>,
    );
    await screen.findByText("4");

    expect(cardHref("dashboard:inbox.applications.label")).toBe("/admin/review");
    expect(cardHref("dashboard:inbox.jobs.label")).toBe("/admin/review?tab=jobs");
    expect(cardHref("dashboard:inbox.companies.label")).toBe("/admin/review?tab=companies");
  });
});

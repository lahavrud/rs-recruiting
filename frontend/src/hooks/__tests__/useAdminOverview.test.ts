/**
 * Guards the #1051 fix: the admin-overview read is shared + deduplicated so the
 * several admin surfaces that consume it (Sidebar + dashboard widgets) don't
 * each fire their own `GET /api/admin/overview` on mount.
 */
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAdminOverviewShared,
  resetAdminOverviewShared,
  useAdminOverview,
} from "@/hooks/useAdminOverview";
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
  mockGet.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("getAdminOverviewShared", () => {
  it("shares a single request across concurrent callers", async () => {
    let resolve!: (v: unknown) => void;
    mockGet.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );

    const p1 = getAdminOverviewShared();
    const p2 = getAdminOverviewShared();
    expect(mockGet).toHaveBeenCalledTimes(1);

    resolve({ data: PAYLOAD });
    expect(await p1).toEqual(PAYLOAD);
    expect(await p2).toEqual(PAYLOAD);
  });

  it("fetches fresh once the previous request has settled (no resolved cache)", async () => {
    mockGet.mockResolvedValue({ data: PAYLOAD });

    await getAdminOverviewShared();
    await getAdminOverviewShared();

    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("refetches after a rejection instead of latching the failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("boom"));
    await expect(getAdminOverviewShared()).rejects.toThrow("boom");

    mockGet.mockResolvedValueOnce({ data: PAYLOAD });
    expect(await getAdminOverviewShared()).toEqual(PAYLOAD);
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("starts a fresh request when the in-flight one is reset mid-flight", async () => {
    let resolveFirst!: (v: unknown) => void;
    mockGet.mockReturnValueOnce(
      new Promise((r) => {
        resolveFirst = r;
      }),
    );
    const p1 = getAdminOverviewShared(); // in-flight, unresolved

    resetAdminOverviewShared(); // abandon it
    mockGet.mockResolvedValueOnce({ data: PAYLOAD });
    const p2 = getAdminOverviewShared(); // must start a new request

    expect(mockGet).toHaveBeenCalledTimes(2);
    resolveFirst({ data: PAYLOAD });
    await Promise.all([p1, p2]);
  });
});

describe("useAdminOverview", () => {
  it("fetches and exposes the payload when enabled", async () => {
    mockGet.mockResolvedValue({ data: PAYLOAD });

    const { result } = renderHook(() => useAdminOverview());

    await waitFor(() => expect(result.current.data).toEqual(PAYLOAD));
  });

  it("does not fetch when disabled (e.g. the Sidebar for a non-admin)", () => {
    mockGet.mockResolvedValue({ data: PAYLOAD });

    renderHook(() => useAdminOverview(false));

    expect(mockGet).not.toHaveBeenCalled();
  });
});

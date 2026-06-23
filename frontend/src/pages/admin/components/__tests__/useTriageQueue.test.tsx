import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTriageQueue } from "@/pages/admin/components/useTriageQueue";
import { ApplicationStatus, type ApplicationWithDetails } from "@/types/api";

// ── Mocks ─────────────────────────────────────────────────────────────────
// Hoisted so they're available before the service modules are evaluated.
const { mockGetApplications, mockGetActiveCompanies } = vi.hoisted(() => ({
  mockGetApplications: vi.fn(),
  mockGetActiveCompanies: vi.fn(),
}));

vi.mock("@/services/adminApplications", () => ({
  getApplications: mockGetApplications,
}));
vi.mock("@/services/adminCompanies", () => ({
  getActiveCompanies: mockGetActiveCompanies,
}));

// ── Fixtures ──────────────────────────────────────────────────────────────

function makeApp(
  id: number,
  overrides: Partial<ApplicationWithDetails> = {},
): ApplicationWithDetails {
  return {
    id,
    job_id: 100,
    candidate_id: 200 + id,
    status: ApplicationStatus.NEW,
    admin_notes: null,
    service_concept: null,
    salary_expectations: null,
    strength: null,
    growth_area: null,
    created_at: "2026-05-29T10:00:00Z",
    updated_at: "2026-05-29T10:00:00Z",
    job: {
      id: 100,
      company_id: 7,
      title: "Manager",
      short_description: "",
      description: "",
      requirements: [],
      tags: [],
      is_featured: false,
      location: "Tel Aviv",
      salary_min: 10000,
      salary_max: 20000,
      status: "ACTIVE" as never,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z",
    },
    candidate: {
      id: 200 + id,
      full_name: `Candidate ${id}`,
      email: `c${id}@example.com`,
      phone: "0500000000",
      resume_path: null,
      linkedin_url: null,
      created_at: "2026-05-01T00:00:00Z",
    },
    ...overrides,
  };
}

function appsPage(items: ApplicationWithDetails[], next_cursor: string | null = null) {
  return { items, next_cursor };
}

function companiesPage() {
  return {
    items: [
      {
        id: 7,
        company_profile: { id: 7, name: "Acme Boutique" } as never,
      },
    ] as never[],
    next_cursor: null,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockGetApplications.mockReset();
  mockGetActiveCompanies.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useTriageQueue", () => {
  it("loads NEW applications and joins the company name", async () => {
    mockGetApplications.mockResolvedValueOnce(appsPage([makeApp(1), makeApp(2)]));
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeNull();
    expect(result.current.items).toHaveLength(2);
    expect(result.current.items[0].id).toBe(1);
    expect(result.current.items[0].companyName).toBe("Acme Boutique");
    // The hook should request only NEW applications
    expect(mockGetApplications).toHaveBeenCalledWith(
      expect.objectContaining({ status: ApplicationStatus.NEW, limit: 100 }),
      expect.any(AbortSignal),
    );
  });

  it("falls back to an em-dash when no matching company is found", async () => {
    mockGetApplications.mockResolvedValueOnce(
      appsPage([makeApp(1, { job: { ...makeApp(1).job, company_id: 999 } })]),
    );
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items[0].companyName).toBe("—");
  });

  it("returns an empty list when the API has no NEW applications", async () => {
    mockGetApplications.mockResolvedValueOnce(appsPage([]));
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("surfaces an error when the apps fetch rejects", async () => {
    mockGetApplications.mockRejectedValueOnce(new Error("network down"));
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.items).toEqual([]);
  });

  it("drains cursor pages until next_cursor is null", async () => {
    // First page has next_cursor → hook calls a second time with the cursor
    mockGetApplications
      .mockResolvedValueOnce(appsPage([makeApp(1), makeApp(2)], "cur-2"))
      .mockResolvedValueOnce(appsPage([makeApp(3)], null));
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(3);
    expect(result.current.items.map((it) => it.id)).toEqual([1, 2, 3]);
    expect(mockGetApplications).toHaveBeenCalledTimes(2);
    expect(mockGetApplications).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ cursor: "cur-2" }),
      expect.any(AbortSignal),
    );
  });

  it("stops after MAX_PAGES pages to avoid unbounded fetching", async () => {
    // Every page returns a cursor, but the hook should cap at 5 pages
    mockGetApplications.mockResolvedValue(
      appsPage([makeApp(1)], "always-more"),
    );
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // 5 pages × 1 item each
    expect(result.current.items).toHaveLength(5);
    expect(mockGetApplications).toHaveBeenCalledTimes(5);
  });

  it("reload() refetches on demand", async () => {
    mockGetApplications.mockResolvedValueOnce(appsPage([makeApp(1)]));
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    const { result } = renderHook(() => useTriageQueue());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(1);

    // Set up second response
    mockGetApplications.mockResolvedValueOnce(
      appsPage([makeApp(1), makeApp(2), makeApp(3)]),
    );
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage());

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.items).toHaveLength(3);
  });
});

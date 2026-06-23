/**
 * Decision-flow integration tests for the triage page.
 *
 * Mocks the service layer (queue fetch + status update) and asserts the
 * end-to-end click-to-API path. The carousel animation and gesture state
 * are intentionally NOT exercised here — those would require fake timers
 * and DOM-level event simulation that adds noise. The decision logic is
 * what causes data loss when it breaks, so that's the priority.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n"; // initialize i18next so t() resolves to real Hebrew strings
import Toaster from "@/components/ui/Toaster";
import { ToastProvider } from "@/contexts/ToastContext";
import AdminApplicationsTriagePage from "@/pages/admin/AdminApplicationsTriagePage";
import { ApplicationStatus, type ApplicationWithDetails } from "@/types/api";

// ── Service mocks ─────────────────────────────────────────────────────────

const {
  mockGetApplications,
  mockGetActiveCompanies,
  mockUpdateApplicationStatus,
} = vi.hoisted(() => ({
  mockGetApplications: vi.fn(),
  mockGetActiveCompanies: vi.fn(),
  mockUpdateApplicationStatus: vi.fn(),
}));

vi.mock("@/services/adminApplications", () => ({
  getApplications: mockGetApplications,
  updateApplicationStatus: mockUpdateApplicationStatus,
}));
vi.mock("@/services/adminCompanies", () => ({
  getActiveCompanies: mockGetActiveCompanies,
}));

// ── Fixtures ──────────────────────────────────────────────────────────────

function makeApp(id: number, name: string): ApplicationWithDetails {
  return {
    id,
    job_id: 100,
    candidate_id: 200 + id,
    status: ApplicationStatus.NEW,
    admin_notes: null,
    service_concept: "תפיסה",
    salary_expectations: null,
    strength: null,
    growth_area: null,
    created_at: "2026-05-29T10:00:00Z",
    updated_at: "2026-05-29T10:00:00Z",
    job: {
      id: 100,
      company_id: 7,
      title: "מנהל",
      short_description: "",
      description: "",
      requirements: [],
      tags: [],
      is_featured: false,
      location: "תל אביב",
      salary_min: 10000,
      salary_max: 20000,
      status: "ACTIVE" as never,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z",
    },
    candidate: {
      id: 200 + id,
      full_name: name,
      email: `c${id}@example.com`,
      phone: "0500000000",
      resume_path: null,
      linkedin_url: null,
      created_at: "2026-05-01T00:00:00Z",
    },
  };
}

const companiesPage = {
  items: [
    { id: 7, company_profile: { id: 7, name: "סטודיו זהבי" } as never },
  ] as never[],
  next_cursor: null,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/admin/applications/triage"]}>
      <ToastProvider>
        <AdminApplicationsTriagePage />
        <Toaster />
      </ToastProvider>
    </MemoryRouter>,
  );
}

// ── Lifecycle ─────────────────────────────────────────────────────────────

beforeEach(() => {
  mockGetApplications.mockReset();
  mockGetActiveCompanies.mockReset();
  mockUpdateApplicationStatus.mockReset();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe("AdminApplicationsTriagePage — decision flow", () => {
  it("shows a loading state, then renders the first candidate", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל אברהמי"), makeApp(2, "יואב כהן")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);

    renderPage();
    expect(screen.getByText(/טוען מועמדים/)).toBeInTheDocument();

    expect(await screen.findByText("מיכל אברהמי")).toBeInTheDocument();
  });

  it("renders the empty state when there are no NEW applications", async () => {
    mockGetApplications.mockResolvedValueOnce({ items: [], next_cursor: null });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);

    renderPage();
    expect(
      await screen.findByText(/אין כרגע מועמדים חדשים לסקירה/),
    ).toBeInTheDocument();
  });

  it("renders an error state when the fetch fails", async () => {
    mockGetApplications.mockRejectedValueOnce(new Error("boom"));
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);

    renderPage();
    expect(
      await screen.findByText(/אירעה שגיאה בטעינת המועמדים/),
    ).toBeInTheDocument();
  });

  it("approve button calls updateApplicationStatus with APPROVED_BY_ADMIN", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל"), makeApp(2, "יואב")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);
    mockUpdateApplicationStatus.mockResolvedValue({} as never);

    renderPage();
    await screen.findByText("מיכל");

    fireEvent.click(screen.getByRole("button", { name: /^אישור$/ }));

    expect(mockUpdateApplicationStatus).toHaveBeenCalledWith(1, {
      status: ApplicationStatus.APPROVED_BY_ADMIN,
    });
    // The undo button only renders inside the UndoToast — its presence is
    // the cleanest signal that the optimistic decision committed.
    expect(
      await screen.findByRole("button", { name: /^בטל$/ }),
    ).toBeInTheDocument();
  });

  it("reject button calls updateApplicationStatus with REJECTED", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל"), makeApp(2, "יואב")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);
    mockUpdateApplicationStatus.mockResolvedValue({} as never);

    renderPage();
    await screen.findByText("מיכל");

    fireEvent.click(screen.getByRole("button", { name: /^דחייה$/ }));

    expect(mockUpdateApplicationStatus).toHaveBeenCalledWith(1, {
      status: ApplicationStatus.REJECTED,
    });
    expect(
      await screen.findByRole("button", { name: /^בטל$/ }),
    ).toBeInTheDocument();
  });

  it("rolls back local state and shows an error toast when save fails", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל"), makeApp(2, "יואב")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);
    mockUpdateApplicationStatus.mockRejectedValueOnce(new Error("500"));

    renderPage();
    await screen.findByText("מיכל");

    fireEvent.click(screen.getByRole("button", { name: /^אישור$/ }));

    // Error toast surfaces
    expect(
      await screen.findByText(/לא הצלחנו לשמור את ההחלטה/),
    ).toBeInTheDocument();
    // The undo affordance from the optimistic toast should also be gone
    // (rollback hides pendingUndo), and the revisit banner on the prev card
    // disappears because decisions[appId] was deleted.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /^בטל$/ })).not.toBeInTheDocument(),
    );
  });

  it("undo button fires updateApplicationStatus(NEW)", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל"), makeApp(2, "יואב")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);
    mockUpdateApplicationStatus.mockResolvedValue({} as never);

    renderPage();
    await screen.findByText("מיכל");

    fireEvent.click(screen.getByRole("button", { name: /^דחייה$/ }));
    // Wait for the optimistic toast to appear (its undo button is unique)
    const undoBtn = await screen.findByRole("button", { name: /^בטל$/ });

    // Undo from the toast
    fireEvent.click(undoBtn);

    expect(mockUpdateApplicationStatus).toHaveBeenLastCalledWith(1, {
      status: ApplicationStatus.NEW,
    });
  });

  it("keyboard A approves the current candidate", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל"), makeApp(2, "יואב")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);
    mockUpdateApplicationStatus.mockResolvedValue({} as never);

    renderPage();
    await screen.findByText("מיכל");

    fireEvent.keyDown(window, { key: "a" });

    expect(mockUpdateApplicationStatus).toHaveBeenCalledWith(1, {
      status: ApplicationStatus.APPROVED_BY_ADMIN,
    });
  });

  it("keyboard R rejects the current candidate", async () => {
    mockGetApplications.mockResolvedValueOnce({
      items: [makeApp(1, "מיכל"), makeApp(2, "יואב")],
      next_cursor: null,
    });
    mockGetActiveCompanies.mockResolvedValueOnce(companiesPage);
    mockUpdateApplicationStatus.mockResolvedValue({} as never);

    renderPage();
    await screen.findByText("מיכל");

    fireEvent.keyDown(window, { key: "r" });

    expect(mockUpdateApplicationStatus).toHaveBeenCalledWith(1, {
      status: ApplicationStatus.REJECTED,
    });
  });
});

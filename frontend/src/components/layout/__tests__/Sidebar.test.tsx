import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Sidebar from "@/components/layout/Sidebar";
import i18n from "@/i18n";
import { UserRole } from "@/types/enums";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { role: UserRole.ADMIN } }),
}));
vi.mock("@/hooks/useAdminOverview", () => ({
  useAdminOverview: () => ({
    data: { inbox: { pending_companies: 2, pending_jobs: 3, new_applications: 4 } },
  }),
}));

describe("Sidebar (admin)", () => {
  it("links to the review queue with the combined pending count", () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen onClose={() => {}} />
      </MemoryRouter>,
    );

    const links = screen.getAllByRole("link", { name: new RegExp(i18n.t("nav:reviewQueue")) });
    expect(links[0]).toHaveAttribute("href", "/admin/review");
    expect(links[0]).toHaveTextContent("9");
  });
});

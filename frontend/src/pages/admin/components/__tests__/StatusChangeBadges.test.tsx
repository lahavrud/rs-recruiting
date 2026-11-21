import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";
import StatusChangeBadges from "@/pages/admin/components/StatusChangeBadges";

const label = (status: string) => i18n.t(`admin:applications.statusLabels.${status}`);

describe("StatusChangeBadges", () => {
  it("renders the from and to statuses of a FROM->TO detail", () => {
    render(<StatusChangeBadges detail="OFFER->JOB_CLOSED" />);

    expect(screen.getByText(label("OFFER"))).toBeInTheDocument();
    expect(screen.getByText(label("JOB_CLOSED"))).toBeInTheDocument();
    expect(screen.getByText("←")).toBeInTheDocument();
  });

  it("shows only the new status for a legacy cascade detail", () => {
    render(<StatusChangeBadges detail="JOB_CLOSED (cascade, job 7)" />);

    expect(screen.getByText(label("JOB_CLOSED"))).toBeInTheDocument();
    expect(screen.queryByText("←")).not.toBeInTheDocument();
    expect(screen.queryByText(/cascade/)).not.toBeInTheDocument();
  });
});

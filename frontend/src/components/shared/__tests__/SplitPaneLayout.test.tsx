import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SplitPaneLayout from "@/components/shared/SplitPaneLayout";

function renderLayout(recordPresent: boolean) {
  return render(
    <SplitPaneLayout
      rail={<p>rail</p>}
      record={<p>record</p>}
      recordPresent={recordPresent}
      showListLabel="show list"
      hideListLabel="hide list"
    />,
  );
}

describe("SplitPaneLayout", () => {
  it("opens the rail when mounted with no record selected", () => {
    renderLayout(false);
    expect(screen.getByRole("button", { name: "hide list" })).toBeInTheDocument();
  });

  it("collapses the rail when mounted with a record selected", () => {
    renderLayout(true);
    expect(screen.getByRole("button", { name: "show list" })).toBeInTheDocument();
  });

  it("collapses the rail once a record gets selected", () => {
    const { rerender } = renderLayout(false);
    rerender(
      <SplitPaneLayout
        rail={<p>rail</p>}
        record={<p>record</p>}
        recordPresent
        showListLabel="show list"
        hideListLabel="hide list"
      />,
    );
    expect(screen.getByRole("button", { name: "show list" })).toBeInTheDocument();
  });
});

import type { ReactNode } from "react";

import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import AdminRoute from "@/components/guards/AdminRoute";
import CandidateRoute from "@/components/guards/CandidateRoute";
import CompanyRoute from "@/components/guards/CompanyRoute";
import ProtectedRoute from "@/components/guards/ProtectedRoute";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";

function loggingOutCtx(): AuthContextType {
  return {
    user: null,
    isAuthenticated: false,
    isLoggingOut: true,
    login: async () => {},
    logout: () => {},
  };
}

function renderWithCtx(guard: ReactNode) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={loggingOutCtx()}>{guard}</AuthContext.Provider>
    </MemoryRouter>,
  );
}

/**
 * When isLoggingOut=true the route guards must render null (not <Navigate to="/login">)
 * so the page-replacement completes without a flash of the login page.
 */
describe("route guards — isLoggingOut sentinel", () => {
  it("AdminRoute renders null while isLoggingOut=true", () => {
    const { container } = renderWithCtx(
      <AdminRoute><div>child</div></AdminRoute>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("ProtectedRoute renders null while isLoggingOut=true", () => {
    const { container } = renderWithCtx(
      <ProtectedRoute><div>child</div></ProtectedRoute>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("CompanyRoute renders null while isLoggingOut=true", () => {
    const { container } = renderWithCtx(
      <CompanyRoute><div>child</div></CompanyRoute>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("CandidateRoute renders null while isLoggingOut=true", () => {
    const { container } = renderWithCtx(
      <CandidateRoute><div>child</div></CandidateRoute>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

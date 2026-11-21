import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AdminRoute from "@/components/guards/AdminRoute";
import CandidateRoute from "@/components/guards/CandidateRoute";
import CompanyRoute from "@/components/guards/CompanyRoute";
import ProtectedRoute from "@/components/guards/ProtectedRoute";
import { AuthContext, type AuthContextType, AuthUser  } from "@/contexts/AuthContext";
import { UserRole } from "@/types/enums";
function makeCtx(user: AuthUser | null): AuthContextType {
  return {
    user,
    isAuthenticated: user !== null,
    isLoggingOut: false,
    login: async () => {},
    logout: () => {},
  };
}

function makeUser(role: string, mfaEnabled = true): AuthUser {
  return { id: "1", email: "test@example.com", role: role as AuthUser["role"], mfaEnabled };
}

function renderGuard(guard: ReactNode, ctx: AuthContextType, at = "/guarded") {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <AuthContext.Provider value={ctx}>
        <Routes>
          <Route path="/guarded" element={guard} />
          <Route
            path="/admin/mfa-setup"
            element={at === "/admin/mfa-setup" ? guard : <div data-testid="mfa-setup" />}
          />
          <Route path="/login" element={<div data-testid="login-page" />} />
          <Route path="/dashboard" element={<div data-testid="dashboard-page" />} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("route guards — unauthenticated redirects to /login", () => {
  const unauthCtx = makeCtx(null);

  it("AdminRoute", () => {
    renderGuard(
      <AdminRoute>
        <div data-testid="child" />
      </AdminRoute>,
      unauthCtx,
    );
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("CompanyRoute", () => {
    renderGuard(
      <CompanyRoute>
        <div data-testid="child" />
      </CompanyRoute>,
      unauthCtx,
    );
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("CandidateRoute", () => {
    renderGuard(
      <CandidateRoute>
        <div data-testid="child" />
      </CandidateRoute>,
      unauthCtx,
    );
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("ProtectedRoute", () => {
    renderGuard(
      <ProtectedRoute>
        <div data-testid="child" />
      </ProtectedRoute>,
      unauthCtx,
    );
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });
});

describe("route guards — wrong role redirects to /dashboard", () => {
  it("AdminRoute rejects COMPANY", () => {
    renderGuard(
      <AdminRoute>
        <div data-testid="child" />
      </AdminRoute>,
      makeCtx(makeUser(UserRole.COMPANY)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("AdminRoute rejects CANDIDATE", () => {
    renderGuard(
      <AdminRoute>
        <div data-testid="child" />
      </AdminRoute>,
      makeCtx(makeUser(UserRole.CANDIDATE)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
  });

  it("CompanyRoute rejects ADMIN", () => {
    renderGuard(
      <CompanyRoute>
        <div data-testid="child" />
      </CompanyRoute>,
      makeCtx(makeUser(UserRole.ADMIN)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("CandidateRoute rejects ADMIN", () => {
    renderGuard(
      <CandidateRoute>
        <div data-testid="child" />
      </CandidateRoute>,
      makeCtx(makeUser(UserRole.ADMIN)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });
});

describe("route guards — correct role renders children", () => {
  it("AdminRoute renders children for ADMIN", () => {
    renderGuard(
      <AdminRoute>
        <div data-testid="child" />
      </AdminRoute>,
      makeCtx(makeUser(UserRole.ADMIN)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("CompanyRoute renders children for COMPANY", () => {
    renderGuard(
      <CompanyRoute>
        <div data-testid="child" />
      </CompanyRoute>,
      makeCtx(makeUser(UserRole.COMPANY)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("CandidateRoute renders children for CANDIDATE", () => {
    renderGuard(
      <CandidateRoute>
        <div data-testid="child" />
      </CandidateRoute>,
      makeCtx(makeUser(UserRole.CANDIDATE)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("ProtectedRoute renders children for any authenticated user", () => {
    renderGuard(
      <ProtectedRoute>
        <div data-testid="child" />
      </ProtectedRoute>,
      makeCtx(makeUser(UserRole.COMPANY)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });
});

describe("route guards — admin without MFA must enrol (#1177)", () => {
  const unenrolled = makeCtx(makeUser(UserRole.ADMIN, false));

  it("AdminRoute sends an unenrolled admin to setup", () => {
    renderGuard(
      <AdminRoute>
        <div data-testid="child" />
      </AdminRoute>,
      unenrolled,
    );
    expect(screen.getByTestId("mfa-setup")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("AdminRoute lets an unenrolled admin reach the setup page itself", () => {
    renderGuard(
      <AdminRoute>
        <div data-testid="child" />
      </AdminRoute>,
      unenrolled,
      "/admin/mfa-setup",
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("ProtectedRoute sends an unenrolled admin to setup", () => {
    renderGuard(
      <ProtectedRoute>
        <div data-testid="child" />
      </ProtectedRoute>,
      unenrolled,
    );
    expect(screen.getByTestId("mfa-setup")).toBeDefined();
  });

  it("ProtectedRoute ignores MFA for non-admins", () => {
    renderGuard(
      <ProtectedRoute>
        <div data-testid="child" />
      </ProtectedRoute>,
      makeCtx(makeUser(UserRole.CANDIDATE, false)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthContext, type AuthContextType } from "@/contexts/AuthContext";
import type { AuthUser } from "@/contexts/AuthContext";
import { UserRole } from "@/types/api";
import AdminRoute from "@/components/guards/AdminRoute";
import CompanyRoute from "@/components/guards/CompanyRoute";
import CandidateRoute from "@/components/guards/CandidateRoute";
import ProtectedRoute from "@/components/guards/ProtectedRoute";

function makeCtx(user: AuthUser | null): AuthContextType {
  return {
    user,
    isAuthenticated: user !== null,
    loggingOut: false,
    login: async () => {},
    logout: () => {},
  };
}

function makeUser(role: string): AuthUser {
  return { id: "1", email: "test@example.com", role: role as AuthUser["role"] };
}

function renderGuard(guard: ReactNode, ctx: AuthContextType) {
  return render(
    <MemoryRouter initialEntries={["/guarded"]}>
      <AuthContext.Provider value={ctx}>
        <Routes>
          <Route path="/guarded" element={guard} />
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
    renderGuard(<AdminRoute><div data-testid="child" /></AdminRoute>, unauthCtx);
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("CompanyRoute", () => {
    renderGuard(<CompanyRoute><div data-testid="child" /></CompanyRoute>, unauthCtx);
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("CandidateRoute", () => {
    renderGuard(<CandidateRoute><div data-testid="child" /></CandidateRoute>, unauthCtx);
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("ProtectedRoute", () => {
    renderGuard(<ProtectedRoute><div data-testid="child" /></ProtectedRoute>, unauthCtx);
    expect(screen.getByTestId("login-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });
});

describe("route guards — wrong role redirects to /dashboard", () => {
  it("AdminRoute rejects COMPANY", () => {
    renderGuard(
      <AdminRoute><div data-testid="child" /></AdminRoute>,
      makeCtx(makeUser(UserRole.COMPANY)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("AdminRoute rejects CANDIDATE", () => {
    renderGuard(
      <AdminRoute><div data-testid="child" /></AdminRoute>,
      makeCtx(makeUser(UserRole.CANDIDATE)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
  });

  it("CompanyRoute rejects ADMIN", () => {
    renderGuard(
      <CompanyRoute><div data-testid="child" /></CompanyRoute>,
      makeCtx(makeUser(UserRole.ADMIN)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("CandidateRoute rejects ADMIN", () => {
    renderGuard(
      <CandidateRoute><div data-testid="child" /></CandidateRoute>,
      makeCtx(makeUser(UserRole.ADMIN)),
    );
    expect(screen.getByTestId("dashboard-page")).toBeDefined();
    expect(screen.queryByTestId("child")).toBeNull();
  });
});

describe("route guards — correct role renders children", () => {
  it("AdminRoute renders children for ADMIN", () => {
    renderGuard(
      <AdminRoute><div data-testid="child" /></AdminRoute>,
      makeCtx(makeUser(UserRole.ADMIN)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("CompanyRoute renders children for COMPANY", () => {
    renderGuard(
      <CompanyRoute><div data-testid="child" /></CompanyRoute>,
      makeCtx(makeUser(UserRole.COMPANY)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("CandidateRoute renders children for CANDIDATE", () => {
    renderGuard(
      <CandidateRoute><div data-testid="child" /></CandidateRoute>,
      makeCtx(makeUser(UserRole.CANDIDATE)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("ProtectedRoute renders children for any authenticated user", () => {
    renderGuard(
      <ProtectedRoute><div data-testid="child" /></ProtectedRoute>,
      makeCtx(makeUser(UserRole.COMPANY)),
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });
});

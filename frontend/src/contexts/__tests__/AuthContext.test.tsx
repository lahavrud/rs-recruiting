import { useContext } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { AuthContext, AuthProvider } from "@/contexts/AuthContext";
import { UserRole } from "@/types/enums";

vi.mock("@sentry/react", () => ({ setUser: vi.fn() }));

const { mockLogout, mockRefreshTokens } = vi.hoisted(() => ({
  mockLogout: vi.fn(),
  mockRefreshTokens: vi.fn(),
}));
vi.mock("@/services/auth", () => ({
  login: vi.fn(),
  logout: mockLogout,
  refreshTokens: mockRefreshTokens,
}));

const ACCESS_TOKEN_KEY = "access_token";

function makeJwt(payload: Record<string, unknown>): string {
  const toBase64Url = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
  return `${toBase64Url({ alg: "HS256", typ: "JWT" })}.${toBase64Url(payload)}.fakesig`;
}

function Consumer() {
  const ctx = useContext(AuthContext);
  if (!ctx) return <div data-testid="no-ctx" />;
  return (
    <>
      <span data-testid="authenticated">{String(ctx.isAuthenticated)}</span>
      <span data-testid="isInitializing">{String(ctx.isInitializing)}</span>
      <span data-testid="role">{ctx.user?.role ?? "none"}</span>
    </>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockLogout.mockClear();
  mockRefreshTokens.mockReset();
});

describe("AuthContext initial state", () => {
  it("populates user from a valid token in localStorage (no refresh needed)", async () => {
    const token = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) + 3600,
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("isInitializing").textContent).toBe("false");
    expect(screen.getByTestId("role").textContent).toBe(UserRole.ADMIN);
    expect(mockRefreshTokens).not.toHaveBeenCalled();
  });

  it("attempts silent refresh when access token is expired", async () => {
    const expiredToken = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) - 1,
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, expiredToken);

    const freshToken = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) + 3600,
    });
    mockRefreshTokens.mockResolvedValue({ access_token: freshToken });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    // During refresh probe, isInitializing=true and not authenticated
    expect(screen.getByTestId("isInitializing").textContent).toBe("true");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");

    await waitFor(() =>
      expect(screen.getByTestId("isInitializing").textContent).toBe("false"),
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it("stays unauthenticated when probe fails for an expired token (no valid cookie)", async () => {
    const expiredToken = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) - 1,
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, expiredToken);
    mockRefreshTokens.mockRejectedValue(new Error("401"));

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("isInitializing").textContent).toBe("false"),
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it("does not probe and shows login immediately when localStorage is empty", () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    // No probe fired — isInitializing starts and stays false for users with no token
    expect(screen.getByTestId("isInitializing").textContent).toBe("false");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("role").textContent).toBe("none");
    expect(mockRefreshTokens).not.toHaveBeenCalled();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it("does not call logoutService for an expired token", async () => {
    const token = makeJwt({
      sub: "user-42",
      email: "admin@example.com",
      role: UserRole.ADMIN,
      exp: Math.floor(Date.now() / 1000) - 1,
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
    mockRefreshTokens.mockRejectedValue(new Error("401"));

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("isInitializing").textContent).toBe("false"),
    );
    expect(mockLogout).not.toHaveBeenCalled();
  });
});

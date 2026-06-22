import type { ReactNode } from "react";

import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

/**
 * Wrapper component that redirects to /login if the user is not authenticated.
 * Passes the current path as `state.from` so LoginPage can redirect back after login.
 */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, loggingOut } = useAuth();
  const location = useLocation();

  if (loggingOut) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return children;
}

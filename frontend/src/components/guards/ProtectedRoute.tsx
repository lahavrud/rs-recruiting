import type { ReactNode } from "react";

import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { MFA_SETUP_PATH } from "@/services/api";
import { UserRole } from "@/types/enums";

/**
 * Wrapper component that redirects to /login if the user is not authenticated.
 * Passes the current path as `state.from` so LoginPage can redirect back after login.
 */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, isInitializing, isLoggingOut } = useAuth();
  const location = useLocation();

  if (isLoggingOut || isInitializing) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  // The admin dashboard calls admin endpoints: send an unenrolled admin to
  // set up MFA first, as AdminRoute does.
  if (user?.role === UserRole.ADMIN && !user.mfaEnabled) {
    return <Navigate to={MFA_SETUP_PATH} replace />;
  }

  return children;
}

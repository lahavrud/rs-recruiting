import type { ReactNode } from "react";

import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { MFA_SETUP_PATH } from "@/services/api";
import { UserRole } from "@/types/enums";

/** Renders children only for authenticated admins; redirects otherwise.
 *  An admin without MFA can reach only the setup page (#1177); the API
 *  enforces the same thing, this just avoids a page of 403s. */
export default function AdminRoute({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, isInitializing, isLoggingOut } = useAuth();
  const location = useLocation();

  if (isLoggingOut || isInitializing) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  if (user?.role !== UserRole.ADMIN) return <Navigate to="/dashboard" replace />;
  if (!user.mfaEnabled && location.pathname !== MFA_SETUP_PATH) {
    return <Navigate to={MFA_SETUP_PATH} replace />;
  }
  return <>{children}</>;
}

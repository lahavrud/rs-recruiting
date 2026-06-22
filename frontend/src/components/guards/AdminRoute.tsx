import type { ReactNode } from "react";

import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/api";

/** Renders children only for authenticated admins; redirects otherwise. */
export default function AdminRoute({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, initializing, loggingOut } = useAuth();
  const location = useLocation();

  if (loggingOut || initializing) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  if (user?.role !== UserRole.ADMIN) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

import type { ReactNode } from "react";

import { Navigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { UserRole } from "@/types/api";

/** Renders children only for authenticated company users; redirects otherwise. */
export default function CompanyRoute({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, initializing, loggingOut } = useAuth();
  if (loggingOut || initializing) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role !== UserRole.COMPANY) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

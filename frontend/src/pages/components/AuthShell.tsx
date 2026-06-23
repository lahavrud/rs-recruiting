import type { ReactNode } from "react";

interface AuthShellProps {
  children: ReactNode;
  /** Extra classes appended to the outer container, e.g. to drop the default padding. */
  className?: string;
}

/**
 * Shared centered-screen layout for auth pages (login, register, activate, password
 * reset, etc). Wraps a single child — typically a status card or the form card — in
 * the standard `flex min-h-screen items-center justify-center bg-void px-4 py-8`
 * container so each page doesn't repeat it per render-state.
 */
export default function AuthShell({ children, className = "px-4 py-8" }: AuthShellProps) {
  return (
    <div className={`flex min-h-screen items-center justify-center bg-void ${className}`.trim()}>
      {children}
    </div>
  );
}

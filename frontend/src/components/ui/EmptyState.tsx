import type { ReactNode } from "react";

import Eyebrow from "@/components/ui/Eyebrow";

interface EmptyStateProps {
  eyebrow: string;
  headline: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

/**
 * Empty-state placeholder for list pages: copper eyebrow, gold rule,
 * headline, optional sub, optional CTA. Same visual idiom as `PageHeader`.
 */
export default function EmptyState({
  eyebrow,
  headline,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border border-white/8 bg-card px-6 py-16 text-center ${className}`}
    >
      <Eyebrow>{eyebrow}</Eyebrow>
      <div className="mt-3 h-px w-8 bg-copper/40" />
      <h2 className="mt-5 text-xl font-semibold text-white/85">{headline}</h2>
      {description && (
        <p className="mt-2 max-w-sm text-sm text-white/40">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

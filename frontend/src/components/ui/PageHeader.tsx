import type { ReactNode } from "react";

import Eyebrow from "@/components/ui/Eyebrow";

interface PageHeaderProps {
  eyebrow: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
}

export default function PageHeader({ eyebrow, subtitle, action, className = "" }: PageHeaderProps) {
  return (
    <div
      className={`mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between ${className}`}
    >
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <div className="mt-3 h-px w-8 bg-copper/40" />
        {subtitle && (
          <p className="mt-4 text-sm text-white/40">{subtitle}</p>
        )}
      </div>
      {action && <div className="w-full sm:w-auto sm:shrink-0">{action}</div>}
    </div>
  );
}

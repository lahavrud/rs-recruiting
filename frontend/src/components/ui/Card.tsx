import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
  isHoverable?: boolean;
}

const paddingCls = {
  sm: "p-4",
  md: "p-5",
  lg: "p-6 sm:p-8",
};

export default function Card({
  children,
  className = "",
  padding = "md",
  isHoverable = false,
}: CardProps) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface shadow-sm ${paddingCls[padding]} ${
        isHoverable ? "transition hover:border-copper/30 hover:shadow-md" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

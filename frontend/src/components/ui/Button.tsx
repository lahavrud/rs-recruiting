import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "ghost-dim" | "ghost-danger" | "danger" | "success";
type Size = "xs" | "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

const variantCls: Record<Variant, string> = {
  primary:
    "bg-copper font-medium text-white hover:bg-gold disabled:cursor-not-allowed disabled:opacity-50",
  ghost:
    "border border-white/20 text-white/60 hover:border-white/40 hover:text-white/90 disabled:cursor-not-allowed disabled:opacity-60",
  "ghost-dim":
    "border border-white/20 text-white/60 hover:border-transparent hover:bg-white/6 hover:text-white/50 disabled:cursor-not-allowed disabled:opacity-60",
  "ghost-danger":
    "border border-white/10 text-white/50 hover:border-danger/50 hover:text-danger disabled:cursor-not-allowed disabled:opacity-40",
  danger:
    "border border-danger/40 text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-50",
  success:
    "bg-success/15 font-medium text-success hover:bg-success/25 disabled:cursor-not-allowed disabled:opacity-50",
};

const sizeCls: Record<Size, string> = {
  xs: "px-2 py-1 text-[11px]",
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-2.5 text-sm",
};

export default function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-sm transition ${variantCls[variant]} ${sizeCls[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

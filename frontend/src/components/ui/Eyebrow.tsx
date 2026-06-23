import type { ReactNode } from "react";

type Size = "sm" | "md";

const sizeCls: Record<Size, string> = {
  sm: "text-[10px]",
  md: "text-[11px]",
};

/**
 * Small copper caps label. `sm` (10px) for page headers/eyebrows above a
 * gold rule; `md` (11px) for in-card filter and form section labels.
 * `isDim` reduces opacity to copper/60 for form section use.
 * `as="label"` + `htmlFor` renders a `<label>` element instead of `<p>`.
 */
export default function Eyebrow({
  children,
  size = "sm",
  isDim,
  as: Tag = "p",
  htmlFor,
  className,
}: {
  children: ReactNode;
  size?: Size;
  isDim?: boolean;
  as?: "p" | "label";
  htmlFor?: string;
  className?: string;
}) {
  const colorCls = isDim ? "text-copper/60" : "text-copper";
  const cls = `${sizeCls[size]} font-semibold uppercase tracking-widest ${colorCls}${className ? ` ${className}` : ""}`;
  if (Tag === "label") {
    return <label htmlFor={htmlFor} className={cls}>{children}</label>;
  }
  return <p className={cls}>{children}</p>;
}

import type { CSSProperties, ReactNode } from "react";

type Size = "sm" | "md";
type Color = "copper" | "gold" | "nickel" | "danger";

const sizeCls: Record<Size, string> = {
  sm: "text-[10px]",
  md: "text-[11px]",
};

const colorMap: Record<Color, string> = {
  copper: "text-copper",
  gold: "text-gold",
  nickel: "text-nickel",
  danger: "text-danger",
};

export default function Eyebrow({
  children,
  size = "sm",
  color = "copper",
  isDim,
  as: Tag = "p",
  htmlFor,
  className,
  style,
}: {
  children: ReactNode;
  size?: Size;
  color?: Color;
  isDim?: boolean;
  as?: "p" | "label";
  htmlFor?: string;
  className?: string;
  style?: CSSProperties;
}) {
  const base = colorMap[color];
  const colorCls = isDim ? `${base}/60` : base;
  const cls = `${sizeCls[size]} font-semibold uppercase tracking-widest ${colorCls}${className ? ` ${className}` : ""}`;
  if (Tag === "label") {
    return <label htmlFor={htmlFor} className={cls} style={style}>{children}</label>;
  }
  return <p className={cls} style={style}>{children}</p>;
}

type Variant = "success" | "info" | "copper" | "gold" | "warning" | "danger";

const variantMap: Record<Variant, string> = {
  success: "bg-success/10 text-success",
  info: "bg-info/10 text-info",
  copper: "bg-copper/10 text-copper",
  gold: "bg-gold/10 text-gold",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
};

export default function StatusBadge({
  label,
  colorCls,
  variant,
}: {
  label: string;
  colorCls?: string;
  variant?: Variant;
}) {
  const resolvedCls = variant ? variantMap[variant] : (colorCls ?? "");
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${resolvedCls}`}>
      {label}
    </span>
  );
}

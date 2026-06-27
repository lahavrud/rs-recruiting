import StatusBadge from "@/components/ui/StatusBadge";

const statusMap: { label: string; colorCls: string }[] = [
  { label: "פעיל", colorCls: "bg-success/15 text-success" },
  { label: "ממתין לאישור", colorCls: "bg-warning/15 text-warning" },
  { label: "נדחה", colorCls: "bg-danger/15 text-danger" },
  { label: "טיוטה", colorCls: "bg-white/8 text-white/50" },
  { label: "הושכר", colorCls: "bg-hired/15 text-hired" },
  { label: "בתהליך", colorCls: "bg-info/15 text-info" },
];

export function StatusBadgePreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div className="flex flex-wrap gap-3">
        {statusMap.map((s) => (
          <StatusBadge key={s.label} label={s.label} colorCls={s.colorCls} />
        ))}
      </div>
      <div className="rounded-md border border-white/8 bg-well p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-white/70">מהנדס בניין — TA Ltd</span>
          <StatusBadge label="פעיל" colorCls="bg-success/15 text-success" />
        </div>
      </div>
    </div>
  );
}

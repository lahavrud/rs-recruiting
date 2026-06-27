import FunnelIcon from "@/components/admin/FunnelIcon";

export function FunnelIconPreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">בתוך כפתור סינון</p>
        <div className="flex gap-3">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-sm border border-white/15 px-3 py-1.5 text-sm text-white/60 transition hover:border-copper/40 hover:text-copper"
          >
            <FunnelIcon />
            סינון
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-sm border border-copper/40 bg-copper/10 px-3 py-1.5 text-sm text-copper"
          >
            <FunnelIcon />
            סינון פעיל
          </button>
        </div>
      </div>
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">גדלים ב-SVG</p>
        <div className="flex items-center gap-6 text-white/60">
          <span className="text-xs text-white/30">[size-4 default]</span>
          <FunnelIcon />
          <span className="block size-5 [&>svg]:size-5"><FunnelIcon /></span>
          <span className="block size-6 [&>svg]:size-6"><FunnelIcon /></span>
        </div>
      </div>
    </div>
  );
}

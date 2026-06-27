import KebabButton from "@/components/ui/KebabButton";

export function KebabButtonPreview() {
  return (
    <div className="space-y-8 bg-card p-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">גדלים</p>
        <div className="flex items-center gap-6">
          <div className="flex flex-col items-center gap-2">
            <KebabButton size="sm" aria-label="פעולות" />
            <span className="text-[10px] text-white/35">sm</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <KebabButton size="md" aria-label="פעולות" />
            <span className="text-[10px] text-white/35">md</span>
          </div>
        </div>
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">בשורת טבלה</p>
        <div className="rounded-md border border-white/8 overflow-hidden">
          {["דנה לוי — מהנדסת בניין", "אבי כהן — מנהל פרויקטים"].map((name) => (
            <div key={name} className="flex items-center justify-between border-b border-white/5 px-4 py-3 last:border-0 hover:bg-card-raised">
              <span className="text-sm text-white/70">{name}</span>
              <KebabButton size="sm" aria-label="פעולות" onClick={(e) => e.stopPropagation()} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

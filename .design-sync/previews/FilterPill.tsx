import FilterPill from "@/components/ui/FilterPill";

const locations = ["תל אביב", "ירושלים", "חיפה", "ראשון לציון", "פתח תקווה"];
const types = ["משרה מלאה", "חלקית", "פרילנס", "עבודה מרחוק"];

export function FilterPillPreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ערים</p>
        <div className="flex flex-wrap gap-2">
          <FilterPill isActive={true}>תל אביב</FilterPill>
          {locations.slice(1).map((l) => (
            <FilterPill key={l} isActive={false}>{l}</FilterPill>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">סוג משרה — compact</p>
        <div className="flex flex-wrap gap-1.5">
          {types.map((t, i) => (
            <FilterPill key={t} isActive={i === 0} compact>{t}</FilterPill>
          ))}
        </div>
      </div>
    </div>
  );
}

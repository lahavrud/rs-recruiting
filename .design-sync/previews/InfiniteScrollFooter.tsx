import InfiniteScrollFooter from "@/components/ui/InfiniteScrollFooter";

export function InfiniteScrollFooterPreview() {
  return (
    <div className="space-y-8 bg-card p-8 max-w-sm">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">טוען דף הבא</p>
        <div className="rounded border border-white/6 bg-well px-4 py-3 space-y-2">
          {["אבי כהן", "מיה לוי", "עומר שמיר"].map((name) => (
            <p key={name} className="text-sm text-white/75">{name}</p>
          ))}
          <InfiniteScrollFooter
            sentinelRef={() => {}}
            isFetchingMore
          />
        </div>
        <p className="mt-2 text-xs text-white/35">הסנטינל (div ריק) מתחת לרשימה — IntersectionObserver מפעיל את הטעינה.</p>
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">סוף רשימה (לא טוען)</p>
        <div className="rounded border border-white/6 bg-well px-4 py-3 space-y-2">
          {["אבי כהן", "מיה לוי", "עומר שמיר"].map((name) => (
            <p key={name} className="text-sm text-white/75">{name}</p>
          ))}
          <InfiniteScrollFooter
            sentinelRef={() => {}}
            isFetchingMore={false}
          />
        </div>
        <p className="mt-2 text-xs text-white/35">כשאין טעינה — אין תצוגה גלויה, רק div הסנטינל.</p>
      </div>
    </div>
  );
}

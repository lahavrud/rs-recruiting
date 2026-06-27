import ScoreBadge from "@/components/admin/ScoreBadge";

const entries = [
  { name: "דנה לוי", meta: "מהנדסת בניין — 5 שנות ניסיון", score: 0.91 },
  { name: "אבי כהן", meta: "מנהל פרויקטים — 3 שנות ניסיון", score: 0.72 },
  { name: "מיכל רוזן", meta: "אדריכלית — 2 שנות ניסיון", score: 0.58 },
  { name: "יוסי אביב", meta: "פועל בניין — ניסיון כללי", score: 0.38 },
];

export function ScoreBadgePreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">ציוני התאמה</p>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex flex-col items-center gap-1.5">
            <ScoreBadge score={0.91} />
            <span className="text-[10px] text-white/35">מעולה ≥75%</span>
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <ScoreBadge score={0.68} />
            <span className="text-[10px] text-white/35">טוב ≥55%</span>
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <ScoreBadge score={0.40} />
            <span className="text-[10px] text-white/35">חלש &lt;55%</span>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        {entries.map((e) => (
          <div key={e.name} className="flex items-center gap-3 rounded-sm border border-white/6 bg-well px-3 py-2.5">
            <ScoreBadge score={e.score} />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-white/85">{e.name}</p>
              <p className="text-xs text-white/40">{e.meta}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

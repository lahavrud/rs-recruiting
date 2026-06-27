import { MatchList } from "@/components/admin/MatchList";

const entries = [
  { key: 1, name: "דנה לוי", meta: "מהנדסת בניין — 8 שנות ניסיון", score: 0.91, onClick: () => {} },
  { key: 2, name: "אבי כהן", meta: "מנהל פרויקטים — TA Ltd", score: 0.74, onClick: () => {} },
  { key: 3, name: "מיכל רוזן", meta: "אדריכלית — 3 שנות ניסיון", score: 0.61, onClick: () => {} },
  { key: 4, name: "יוסי אביב", meta: "פועל בניין — ניסיון כללי", score: 0.42, onClick: () => {} },
];

export function MatchListPreview() {
  return (
    <div className="space-y-8 bg-card p-8">
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">עם נתונים</p>
        <MatchList
          entries={entries}
          hasError={false}
          emptyMessage="אין התאמות"
          errorMessage="לא ניתן לטעון"
        />
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק</p>
        <MatchList
          entries={[]}
          hasError={false}
          emptyMessage="לא נמצאו מועמדים מתאימים למשרה זו"
          errorMessage="שגיאה"
        />
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">טוען</p>
        <MatchList
          entries={null}
          hasError={false}
          emptyMessage="אין"
          errorMessage="שגיאה"
        />
      </div>
    </div>
  );
}

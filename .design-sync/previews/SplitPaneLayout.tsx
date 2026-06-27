import SplitPaneLayout from "@/components/admin/SplitPaneLayout";

function MockRailItem({ name, title }: { name: string; title: string }) {
  return (
    <div className="border-b border-white/6 px-4 py-3 hover:bg-card-raised cursor-pointer">
      <p className="text-sm font-medium text-white/85">{name}</p>
      <p className="text-xs text-white/40 mt-0.5">{title}</p>
    </div>
  );
}

function MockRecord() {
  return (
    <div className="p-6 h-full">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper mb-4">פרטי מועמד</p>
      <p className="text-sm text-white/70 leading-6">
        לחץ על מועמד ברשימה כדי לראות את הפרטים כאן. לוח הבקרה מתמוטט אוטומטית
        בעת בחירת רשומה — לחץ על הפס הצדדי כדי לפתוח או לסגור את הרשימה.
      </p>
    </div>
  );
}

export function SplitPaneLayoutPreview() {
  return (
    <div className="bg-page" style={{ height: 400 }}>
      <SplitPaneLayout
        recordPresent
        showListLabel="הצג רשימה"
        hideListLabel="הסתר רשימה"
        rail={
          <div className="h-full bg-void">
            {["אבי כהן", "מיה לוי", "עומר שמיר"].map((name, i) => (
              <MockRailItem key={i} name={name} title={["מנהל תחזוקה", "מנהלת מתקנים", "אחראי בטיחות"][i]} />
            ))}
          </div>
        }
        record={<MockRecord />}
      />
    </div>
  );
}

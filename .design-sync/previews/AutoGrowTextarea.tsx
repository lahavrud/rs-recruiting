import { useState } from "react";
import AutoGrowTextarea from "@/components/ui/AutoGrowTextarea";

export function AutoGrowTextareaPreview() {
  const [v1, setV1] = useState("כותב כאן תיאור משרה...");
  const [v2, setV2] = useState("מחפשים מהנדס בניין מנוסה לתפקיד מאתגר בחברה מובילה.\n\nהתפקיד כולל ניהול פרויקטים, קשר עם לקוחות וגורמים מקצועיים.\n\nנדרשת שליטה בתוכנות תכנון ורישיון ג׳.");
  return (
    <div className="space-y-6 bg-page p-8">
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">קצר (4 שורות מינימום)</p>
        <AutoGrowTextarea
          value={v1}
          onChange={setV1}
          className="w-full rounded-sm border border-white/15 bg-well px-3 py-2 text-sm text-white/85 placeholder:text-white/25 focus:border-copper/50 focus:outline-none"
          placeholder="תיאור..."
          minRows={4}
        />
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">ארוך — מתרחב עם התוכן</p>
        <AutoGrowTextarea
          value={v2}
          onChange={setV2}
          className="w-full rounded-sm border border-white/15 bg-well px-3 py-2 text-sm text-white/85 focus:border-copper/50 focus:outline-none"
          minRows={4}
        />
      </div>
    </div>
  );
}

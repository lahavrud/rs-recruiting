import { useState } from "react";
import SortControl from "@/components/admin/SortControl";

const options = [
  { value: "name:asc", label: "שם — א-ת" },
  { value: "name:desc", label: "שם — ת-א" },
  { value: "date:desc", label: "תאריך — חדש לישן" },
  { value: "date:asc", label: "תאריך — ישן לחדש" },
  { value: "score:desc", label: "ציון — גבוה לנמוך" },
];

export function SortControlPreview() {
  const [sort, setSort] = useState("date:desc");
  return (
    <div className="space-y-4 bg-card p-8 max-w-xs">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">מיון</p>
      <SortControl
        value={sort}
        onChange={(s, o) => setSort(`${s}:${o}`)}
        options={options}
        ariaLabel="מיון רשימה"
      />
      <p className="text-xs text-white/40">נבחר: {options.find((o) => o.value === sort)?.label}</p>
    </div>
  );
}

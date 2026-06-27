import { useState } from "react";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import type { JobRequirementItem } from "@/types/jobs";

const INITIAL: JobRequirementItem[] = [
  { id: 1, text: "5+ שנות ניסיון בניהול מתקנים" },
  { id: 2, text: "רישיון נהיגה בתוקף" },
  { id: 3, text: "שליטה ב-Excel ובמערכות ERP" },
];

export function JobRequirementsInputPreview() {
  const [reqs, setReqs] = useState<JobRequirementItem[]>(INITIAL);
  const [reqs2, setReqs2] = useState<JobRequirementItem[]>([]);
  return (
    <div className="space-y-8 bg-card p-8 max-w-lg">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">עם דרישות (גרור לסדר מחדש)</p>
        <JobRequirementsInput value={reqs} onChange={setReqs} />
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק — לחץ + להוסיף</p>
        <JobRequirementsInput value={reqs2} onChange={setReqs2} />
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">עם שגיאת ולידציה</p>
        <JobRequirementsInput
          value={[{ id: 1, text: "רישיון נהיגה" }]}
          onChange={() => {}}
          error="יש להוסיף לפחות 3 דרישות"
        />
      </div>
    </div>
  );
}

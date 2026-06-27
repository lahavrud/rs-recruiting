import { useState } from "react";
import JobTagsInput from "@/components/ui/JobTagsInput";

export function JobTagsInputPreview() {
  const [tags, setTags] = useState<string[]>(["רכב צמוד", "טלפון נייד", "קרן השתלמות", "ארוחות"]);
  const [tags2, setTags2] = useState<string[]>([]);
  return (
    <div className="space-y-8 bg-card p-8 max-w-lg">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">תגיות מולאות (גרור לסדר מחדש)</p>
        <JobTagsInput value={tags} onChange={setTags} />
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק — הוסף תגית</p>
        <JobTagsInput value={tags2} onChange={setTags2} />
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">עם שגיאה</p>
        <JobTagsInput
          value={["BMS", "כוננות", "משמרות"]}
          onChange={() => {}}
          error="מקסימום 10 תגיות"
        />
      </div>
    </div>
  );
}

import { useState } from "react";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";

const jobTypes = [
  { value: "full_time", label: "משרה מלאה" },
  { value: "part_time", label: "משרה חלקית" },
  { value: "contract", label: "קבלן / פרילנס" },
  { value: "remote", label: "עבודה מרחוק" },
  { value: "internship", label: "התמחות" },
];

const cities = [
  { value: "tlv", label: "תל אביב" },
  { value: "jlm", label: "ירושלים" },
  { value: "hfa", label: "חיפה" },
  { value: "rah", label: "ראשון לציון" },
  { value: "pet", label: "פתח תקווה" },
];

export function SearchableMultiSelectPreview() {
  const [types, setTypes] = useState<string[]>(["full_time", "contract"]);
  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  return (
    <div className="space-y-6 bg-card p-8 max-w-xs">
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">עם 2 ערכים נבחרים</p>
        <SearchableMultiSelect
          values={types}
          onChange={setTypes}
          options={jobTypes}
          placeholder="סוג משרה"
          searchPlaceholder="חיפוש..."
        />
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק — לחץ לפתוח</p>
        <SearchableMultiSelect
          values={selectedCities}
          onChange={setSelectedCities}
          options={cities}
          placeholder="בחר ערים"
          searchPlaceholder="חיפוש עיר..."
        />
      </div>
    </div>
  );
}

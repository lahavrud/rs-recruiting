import { useState } from "react";
import SearchableSelect from "@/components/admin/SearchableSelect";

const cities = [
  { value: "tlv", label: "תל אביב-יפו" },
  { value: "jlm", label: "ירושלים" },
  { value: "hfa", label: "חיפה" },
  { value: "rah", label: "ראשון לציון" },
  { value: "pet", label: "פתח תקווה" },
  { value: "bsh", label: "באר שבע" },
  { value: "net", label: "נתניה" },
  { value: "ash", label: "אשדוד" },
];

export function SearchableSelectPreview() {
  const [city, setCity] = useState<string | null>("tlv");
  const [city2, setCity2] = useState<string | null>(null);
  return (
    <div className="space-y-6 bg-card p-8 max-w-xs">
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">עם ערך נבחר</p>
        <SearchableSelect
          value={city}
          onChange={setCity}
          options={cities}
          placeholder="בחר עיר"
          searchPlaceholder="חיפוש..."
        />
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק — לחץ לפתוח</p>
        <SearchableSelect
          value={city2}
          onChange={setCity2}
          options={cities}
          placeholder="בחר עיר"
          searchPlaceholder="חיפוש..."
        />
      </div>
    </div>
  );
}

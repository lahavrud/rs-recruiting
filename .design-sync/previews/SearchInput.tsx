import SearchInput from "@/components/ui/SearchInput";

export function SearchInputPreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">חיפוש ריק</p>
        <SearchInput onChange={() => {}} placeholder="חפש מועמד..." />
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">עם ערך ו-clear</p>
        <SearchInput onChange={() => {}} value="דנה לוי" isClearable />
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ברוחב מלא</p>
        <SearchInput onChange={() => {}} placeholder="חיפוש משרות..." className="w-full" />
      </div>
    </div>
  );
}

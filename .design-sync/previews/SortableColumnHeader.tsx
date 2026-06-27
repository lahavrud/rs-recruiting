import SortableColumnHeader from "@/components/admin/SortableColumnHeader";

export function SortableColumnHeaderPreview() {
  return (
    <div className="bg-card p-8">
      <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">כותרות עמודות</p>
      <table className="w-full text-xs text-white/50">
        <thead>
          <tr className="border-b border-white/8 bg-well">
            <th className="px-4 py-3 text-start font-normal">
              <SortableColumnHeader label="שם" active={true} order="asc" onClick={() => {}} />
            </th>
            <th className="px-4 py-3 text-start font-normal">
              <SortableColumnHeader label="תאריך" active={true} order="desc" onClick={() => {}} />
            </th>
            <th className="px-4 py-3 text-start font-normal">
              <SortableColumnHeader label="סטטוס" active={false} order="asc" onClick={() => {}} />
            </th>
            <th className="px-4 py-3 text-start font-normal">
              <SortableColumnHeader label="ציון" active={true} order="desc" onClick={() => {}} rank={1} />
            </th>
            <th className="px-4 py-3 text-start font-normal">
              <SortableColumnHeader label="תפקיד" active={true} order="asc" onClick={() => {}} rank={2} />
            </th>
          </tr>
        </thead>
        <tbody>
          {["דנה לוי", "אבי כהן", "מיכל רוזן"].map((name) => (
            <tr key={name} className="border-b border-white/5">
              <td className="px-4 py-3 text-white/70">{name}</td>
              <td className="px-4 py-3">12/06/2025</td>
              <td className="px-4 py-3">פעיל</td>
              <td className="px-4 py-3">82%</td>
              <td className="px-4 py-3">מהנדס</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

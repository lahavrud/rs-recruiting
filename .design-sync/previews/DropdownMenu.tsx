import DropdownMenu, { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/DropdownMenu";
import KebabButton from "@/components/ui/KebabButton";
import Button from "@/components/ui/Button";

export function DropdownMenuPreview() {
  return (
    <div className="space-y-8 bg-card p-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">עם Kebab trigger</p>
        <DropdownMenu trigger={<KebabButton aria-label="פעולות נוספות" />} ariaLabel="פעולות">
          <DropdownMenuItem onSelect={() => {}}>עריכה</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => {}}>שכפול</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => {}} variant="danger">מחיקה</DropdownMenuItem>
        </DropdownMenu>
      </div>
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">עם Button trigger</p>
        <DropdownMenu
          trigger={<Button variant="ghost" size="sm">פעולות ▾</Button>}
          ariaLabel="פעולות"
          align="start"
        >
          <DropdownMenuItem onSelect={() => {}}>ייצוא PDF</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => {}}>שליחה במייל</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => {}} disabled>הדפסה (לא זמין)</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => {}} variant="danger">ארכוב</DropdownMenuItem>
        </DropdownMenu>
      </div>
    </div>
  );
}

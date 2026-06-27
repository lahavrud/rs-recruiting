import Button from "@/components/ui/Button";

export function ButtonPreview() {
  return (
    <div className="space-y-8 bg-card p-8">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">Variants</p>
        <div className="flex flex-wrap gap-3">
          <Button variant="primary">שמור שינויים</Button>
          <Button variant="ghost">ביטול</Button>
          <Button variant="danger">מחק</Button>
          <Button variant="success">אשר</Button>
        </div>
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">Sizes</p>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" size="sm">קטן</Button>
          <Button variant="primary" size="md">בינוני</Button>
          <Button variant="primary" size="lg">גדול</Button>
        </div>
      </div>
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">Disabled</p>
        <div className="flex flex-wrap gap-3">
          <Button variant="primary" disabled>שמור</Button>
          <Button variant="ghost" disabled>ביטול</Button>
          <Button variant="danger" disabled>מחק</Button>
        </div>
      </div>
    </div>
  );
}

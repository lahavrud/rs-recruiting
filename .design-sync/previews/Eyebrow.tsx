import Eyebrow from "@/components/ui/Eyebrow";

export function EyebrowPreview() {
  return (
    <div className="space-y-8 bg-card p-8">
      <div className="space-y-4">
        <Eyebrow>מועמדים</Eyebrow>
        <div className="mt-1 h-px w-8 bg-copper/40" />
      </div>
      <div className="space-y-3">
        <Eyebrow size="md">פרטי מועמד</Eyebrow>
        <Eyebrow size="sm">מידע כללי</Eyebrow>
        <Eyebrow isDim>שדה אופציונלי</Eyebrow>
      </div>
      <div className="rounded-md border border-white/8 bg-well p-4 space-y-3">
        <Eyebrow size="md">פרטים אישיים</Eyebrow>
        <div className="grid gap-3">
          <div className="flex flex-col gap-1">
            <Eyebrow as="label" htmlFor="name" isDim>שם מלא</Eyebrow>
            <input id="name" className="rounded-sm border border-white/15 bg-card px-3 py-1.5 text-sm text-white/80" defaultValue="דנה לוי" />
          </div>
        </div>
      </div>
    </div>
  );
}

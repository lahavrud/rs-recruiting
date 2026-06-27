import SignatureCanvas from "@/components/ui/SignatureCanvas";

export function SignatureCanvasPreview() {
  return (
    <div className="space-y-6 bg-page p-8">
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">חתימה דיגיטלית</p>
        <p className="mb-4 text-xs text-white/40">לחץ וגרור כדי לחתום</p>
        <SignatureCanvas />
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">עם שגיאה</p>
        <SignatureCanvas hasError />
      </div>
    </div>
  );
}

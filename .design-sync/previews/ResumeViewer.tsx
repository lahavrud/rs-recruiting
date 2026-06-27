import { useState } from "react";
import Button from "@/components/ui/Button";
import { ResumeViewer } from "@/components/ui/ResumeViewer";

export function ResumeViewerPreview() {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-6 bg-card p-8">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">צופה קורות חיים</p>
        <p className="mb-4 text-xs text-white/50">
          ResumeViewer מציג קורות חיים על כל המסך — PDF ב-iframe, DOC/DOCX עם כפתור הורדה.
          מסתגר עם Escape או כפתור סגירה.
        </p>
        <Button variant="primary" onClick={() => setOpen(true)}>
          פתח צופה קורות חיים
        </Button>
      </div>

      <div className="rounded border border-white/8 bg-well p-4 text-xs text-white/40 space-y-1">
        <p><span className="text-white/60">PDF</span> → מוצג ב-iframe מובנה</p>
        <p><span className="text-white/60">DOC / DOCX</span> → כפתור הורדה + iOS Web Share</p>
        <p><span className="text-white/60">iOS</span> → תמיד מצב הורדה (WebKit לא מציג PDF מ-blob:)</p>
        <p><span className="text-white/60">404</span> → הודעת "קובץ לא זמין" בלי כפתור הורדה</p>
      </div>

      {open && (
        <ResumeViewer
          candidateName="אבי כהן"
          resumePath="resumes/demo-resume.pdf"
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}

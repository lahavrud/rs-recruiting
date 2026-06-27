import CompanyName from "@/components/ui/CompanyName";

export function CompanyNamePreview() {
  return (
    <div className="space-y-6 bg-card p-8">
      <div className="text-sm text-white/70">
        משרה: מהנדס בניין בכיר • <CompanyName name="TA Group Ltd" />
      </div>
      <div className="rounded-md border border-white/8 bg-well p-4 space-y-1.5">
        <p className="text-lg text-white/90">מנהל פרויקטים בינוי</p>
        <p className="text-sm text-white/45">
          <CompanyName name="Electra Real Estate" /> · תל אביב · משרה מלאה
        </p>
      </div>
      <div className="space-y-2 text-sm">
        <p>מועמד: <span className="text-white/85">אבי כהן</span> → <CompanyName name="M. Kirschenbaum & Sons" /></p>
        <p>חברה נוכחית: <CompanyName name="Dan Hotel Group" /></p>
        <p>חברה שנדחתה: <CompanyName name="City Construction Ltd" className="opacity-50" /></p>
      </div>
    </div>
  );
}

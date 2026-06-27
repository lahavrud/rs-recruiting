import FeaturedRibbon from "@/components/ui/FeaturedRibbon";

function JobCard({ title, company, featured }: { title: string; company: string; featured?: boolean }) {
  return (
    <div className="group relative rounded-lg border border-white/8 bg-card p-5 pt-4">
      {featured && <FeaturedRibbon label="מבוקש" />}
      <p className="text-sm font-semibold text-white/90 mt-1">{title}</p>
      <p className="text-xs text-copper mt-0.5">{company}</p>
      <p className="text-xs text-white/35 mt-2">תל אביב · משרה מלאה</p>
    </div>
  );
}

export function FeaturedRibbonPreview() {
  return (
    <div className="space-y-6 bg-page p-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">סרט "מבוקש" על כרטיסי משרה</p>
        <div className="grid grid-cols-2 gap-4 max-w-lg">
          <JobCard title="מנהל תחזוקה" company="קבוצת עזריאלי" featured />
          <JobCard title="אחראי תשתיות" company="מלון ענבל" />
          <JobCard title="מנהל אחזקה" company="בית חולים איכילוב" featured />
          <JobCard title="מנהל מתקנים" company="בניין הבורסה" />
        </div>
      </div>
      <p className="text-xs text-white/35">ריבון נופל אנימציה מופעלת ב-hover על כרטיס עם class <code className="text-white/60">group</code>.</p>
    </div>
  );
}

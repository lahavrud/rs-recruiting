import PageHeader from "@/components/ui/PageHeader";
import Button from "@/components/ui/Button";

export function PageHeaderPreview() {
  return (
    <div className="space-y-10 bg-page p-8">
      <div>
        <PageHeader eyebrow="מועמדים" />
        <div className="h-px bg-white/5" />
      </div>
      <div>
        <PageHeader
          eyebrow="משרות פתוחות"
          subtitle="ניהול כל המשרות הפעילות והארכיון"
        />
        <div className="h-px bg-white/5" />
      </div>
      <div>
        <PageHeader
          eyebrow="חברות"
          subtitle="ניהול חברות ופרופילי מעסיקים"
          action={<Button variant="primary" size="sm">הוסף חברה</Button>}
        />
        <div className="h-px bg-white/5" />
      </div>
    </div>
  );
}

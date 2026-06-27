import { useState } from "react";
import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Field from "@/components/ui/Field";
import { INPUT_CLS } from "@/styles/forms";

export function DialogPreview() {
  const [smOpen, setSmOpen] = useState(false);
  const [mdOpen, setMdOpen] = useState(false);
  return (
    <div className="space-y-4 bg-card p-8">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper mb-4">גדלי דיאלוג</p>
      <div className="flex gap-3">
        <Button variant="ghost" onClick={() => setSmOpen(true)}>קטן (sm)</Button>
        <Button variant="primary" onClick={() => setMdOpen(true)}>בינוני (md) — טופס</Button>
      </div>

      <Dialog
        open={smOpen}
        onOpenChange={setSmOpen}
        title="פרטי משרה"
        description="כל השדות המסומנים בכוכבית הם שדות חובה."
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSmOpen(false)}>ביטול</Button>
            <Button variant="primary" onClick={() => setSmOpen(false)}>שמור</Button>
          </>
        }
      >
        <p className="text-sm text-white/60">תוכן דיאלוג קטן — לאישורים בסיסיים.</p>
      </Dialog>

      <Dialog
        open={mdOpen}
        onOpenChange={setMdOpen}
        title="עריכת פרטי מועמד"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setMdOpen(false)}>ביטול</Button>
            <Button variant="primary" onClick={() => setMdOpen(false)}>שמור שינויים</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="שם מלא" required>
            <input className={INPUT_CLS} defaultValue="אבי כהן" />
          </Field>
          <Field label="תפקיד מבוקש">
            <input className={INPUT_CLS} defaultValue="מנהל תחזוקה" />
          </Field>
          <Field label="הערות">
            <input className={INPUT_CLS} placeholder="הוסף הערה..." />
          </Field>
        </div>
      </Dialog>
    </div>
  );
}

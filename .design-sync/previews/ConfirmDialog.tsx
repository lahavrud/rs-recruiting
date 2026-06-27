import { useState } from "react";
import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";

export function ConfirmDialogPreview() {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [approveOpen, setApproveOpen] = useState(false);
  return (
    <div className="space-y-4 bg-card p-8">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper mb-4">לחץ לפתוח דיאלוג אישור</p>
      <div className="flex gap-3">
        <Button variant="danger" onClick={() => setDeleteOpen(true)}>מחק מועמד</Button>
        <Button variant="primary" onClick={() => setApproveOpen(true)}>אשר חברה</Button>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="מחיקת מועמד"
        message="האם אתה בטוח שברצונך למחוק את המועמד? פעולה זו אינה הפיכה ותסיר את כל הנתונים הקשורים."
        confirmLabel="מחק לצמיתות"
        variant="danger"
        onConfirm={() => setDeleteOpen(false)}
      />

      <ConfirmDialog
        open={approveOpen}
        onOpenChange={setApproveOpen}
        title="אישור חברה"
        message="האם לאשר את הצטרפות החברה? תישלח הודעת אישור אוטומטית לאיש הקשר."
        confirmLabel="אשר"
        variant="primary"
        onConfirm={() => setApproveOpen(false)}
      />
    </div>
  );
}

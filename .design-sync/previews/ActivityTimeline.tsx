import ActivityTimeline from "@/components/admin/ActivityTimeline";

interface AuditEvent {
  id: number;
  created_at: string;
  action: string;
  actor: string;
}

const EVENTS: AuditEvent[] = [
  { id: 1, created_at: "2025-06-15T10:23:00Z", action: "הועבר לראיון", actor: "שרה לוי" },
  { id: 2, created_at: "2025-06-12T14:05:00Z", action: "נצפה קורות חיים", actor: "אבי כהן" },
  { id: 3, created_at: "2025-06-10T09:17:00Z", action: "נשלחה הודעה למועמד", actor: "שרה לוי" },
  { id: 4, created_at: "2025-06-07T16:44:00Z", action: "נשלח לסקירה", actor: "מיה רז" },
];

export function ActivityTimelinePreview() {
  return (
    <div className="space-y-8 bg-card p-8 max-w-sm">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ציר פעולות</p>
        <ActivityTimeline
          events={EVENTS}
          error={false}
          emptyMessage="אין פעולות רשומות"
          errorMessage="שגיאה בטעינת הפעולות"
          loadingMessage="טוען פעולות..."
          renderItem={(e) => (
            <p className="text-sm text-white/80">
              <span className="font-medium text-white/90">{e.actor}</span> — {e.action}
            </p>
          )}
        />
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">ריק</p>
        <ActivityTimeline
          events={[]}
          error={false}
          emptyMessage="אין פעולות רשומות עדיין"
          errorMessage=""
          loadingMessage=""
          renderItem={() => null}
        />
      </div>

      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">טוען</p>
        <ActivityTimeline
          events={null}
          error={false}
          emptyMessage=""
          errorMessage=""
          loadingMessage="טוען נתונים..."
          renderItem={() => null}
        />
      </div>
    </div>
  );
}

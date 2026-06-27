import { useState } from "react";
import StatusSegmentedControl from "@/components/admin/StatusSegmentedControl";

type AppStatus = "pending" | "review" | "interview" | "offer";

const APP_STATUSES: AppStatus[] = ["pending", "review", "interview", "offer"];

const APP_CONFIG: Record<AppStatus, { sliderCls: string; activeCls: string; dotCls: string }> = {
  pending: {
    sliderCls: "bg-white/6 border-white/15",
    activeCls: "text-white/75",
    dotCls: "bg-white/50",
  },
  review: {
    sliderCls: "bg-info/10 border-info/30",
    activeCls: "text-info",
    dotCls: "bg-info",
  },
  interview: {
    sliderCls: "bg-warning/10 border-warning/30",
    activeCls: "text-warning",
    dotCls: "bg-warning",
  },
  offer: {
    sliderCls: "bg-success/10 border-success/30",
    activeCls: "text-success",
    dotCls: "bg-success",
  },
};

const labels: Record<AppStatus, string> = {
  pending: "ממתין",
  review: "בסקירה",
  interview: "ראיון",
  offer: "הצעה",
};

export function StatusSegmentedControlPreview() {
  const [status, setStatus] = useState<AppStatus>("review");
  return (
    <div className="space-y-6 bg-card p-8 max-w-sm">
      <div>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">סטטוס מועמדות</p>
        <StatusSegmentedControl
          statuses={APP_STATUSES}
          value={status}
          onChange={setStatus}
          config={APP_CONFIG}
          labelFor={(s) => labels[s]}
          ariaLabel="שנה סטטוס מועמדות"
        />
      </div>
      <p className="text-xs text-white/40">סטטוס נוכחי: <span className="text-white/70">{labels[status]}</span></p>
    </div>
  );
}

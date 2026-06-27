import Toaster from "@/components/ui/Toaster";
import { ToastContext, type ToastContextValue } from "@/contexts/toastContext";

const variants: Array<"success" | "error" | "info"> = ["success", "error", "info"];

const variantCls: Record<string, string> = {
  success: "border-success/40 bg-card-raised text-success",
  error: "border-danger/40 bg-card-raised text-danger",
  info: "border-white/15 bg-card-raised text-white/85",
};

const messages: Record<string, string> = {
  success: "הפרופיל עודכן בהצלחה",
  error: "אירעה שגיאה. אנא נסה שוב.",
  info: "המשרה נשמרה כטיוטה",
};

export function ToasterPreview() {
  return (
    <div className="bg-card p-8 space-y-8">
      <div>
        <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">סוגי התראות</p>
        <div className="space-y-2 max-w-sm">
          {variants.map((v) => (
            <div
              key={v}
              className={[
                "rounded-md border px-4 py-3 text-sm font-medium shadow-lg shadow-black/40 text-start",
                variantCls[v],
              ].join(" ")}
            >
              {messages[v]}
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-copper">Toaster חי (ריק)</p>
        <p className="text-xs text-white/35">הרכיב מוסתר כשאין הודעות. מוצב fixed בפינה.</p>
        <ToastContext.Provider value={{ toasts: [], show: () => {}, success: () => {}, error: () => {}, info: () => {}, dismiss: () => {} }}>
          <Toaster />
        </ToastContext.Provider>
      </div>
    </div>
  );
}

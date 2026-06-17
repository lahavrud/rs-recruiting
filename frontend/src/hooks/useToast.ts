import { useContext } from "react";
import { ToastContext, type ToastContextValue } from "@/contexts/toast-context";

/** Fire-and-forget toast helpers. Throws if used outside `<ToastProvider>`. */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a <ToastProvider>");
  }
  return ctx;
}

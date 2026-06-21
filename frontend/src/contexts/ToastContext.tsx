import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ToastContext,
  type Toast,
  type ToastContextValue,
  type ToastVariant,
} from "./toastContext";

const DEFAULT_DURATION_MS = 4000;

interface ProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer != null) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const show = useCallback(
    (
      message: string,
      variant: ToastVariant = "info",
      durationMs = DEFAULT_DURATION_MS,
    ) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, message, variant, duration: durationMs }]);
      if (durationMs > 0) {
        const timer = window.setTimeout(() => dismiss(id), durationMs);
        timers.current.set(id, timer);
      }
    },
    [dismiss],
  );

  const api = useMemo<ToastContextValue>(
    () => ({
      toasts,
      show,
      success: (message, duration) => show(message, "success", duration),
      error: (message, duration) => show(message, "error", duration ?? 6000),
      info: (message, duration) => show(message, "info", duration),
      dismiss,
    }),
    [toasts, show, dismiss],
  );

  // Cleanup all timers on unmount.
  useEffect(() => {
    const map = timers.current;
    return () => {
      map.forEach((id) => window.clearTimeout(id));
      map.clear();
    };
  }, []);

  return <ToastContext.Provider value={api}>{children}</ToastContext.Provider>;
}

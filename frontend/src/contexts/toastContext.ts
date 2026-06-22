import { createContext } from "react";

export type ToastVariant = "success" | "error" | "info";

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
  duration: number;
}

export interface ToastApi {
  show: (message: string, variant?: ToastVariant, durationMs?: number) => void;
  success: (message: string, durationMs?: number) => void;
  error: (message: string, durationMs?: number) => void;
  info: (message: string, durationMs?: number) => void;
  dismiss: (id: number) => void;
}

export interface ToastContextValue extends ToastApi {
  toasts: Toast[];
}

export const ToastContext = createContext<ToastContextValue | null>(null);

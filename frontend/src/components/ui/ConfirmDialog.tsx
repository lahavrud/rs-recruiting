import { useTranslation } from "react-i18next";

import Button from "./Button";
import Dialog from "./Dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "primary" | "danger";
  onConfirm: () => void | Promise<void>;
  isPending?: boolean;
}

/**
 * Confirmation modal that replaces `window.confirm(...)`. The confirm
 * action can be sync or async; `isPending` lets the caller disable the
 * button while a request is in flight.
 */
export default function ConfirmDialog({
  open,
  onOpenChange,
  title,
  message,
  confirmLabel,
  cancelLabel,
  variant = "primary",
  onConfirm,
  isPending = false,
}: ConfirmDialogProps) {
  const { t } = useTranslation('common');
  const confirmText = confirmLabel ?? t("common:confirm");
  const cancelText = cancelLabel ?? t("common:cancel");

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={message}
      size="sm"
      footer={
        <>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            {cancelText}
          </Button>
          <Button
            type="button"
            variant={variant}
            onClick={() => void onConfirm()}
            disabled={isPending}
          >
            {isPending ? t("common:loading") : confirmText}
          </Button>
        </>
      }
    />
  );
}

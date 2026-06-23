import type { ReactNode } from "react";

import * as RadixDialog from "@radix-ui/react-dialog";
import { useTranslation } from "react-i18next";

type Size = "sm" | "md" | "lg";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  /** Footer slot — typically action buttons. */
  footer?: ReactNode;
  size?: Size;
  /**
   * When `true`, clicks on the overlay (or interactions outside the content)
   * will NOT close the dialog. Useful when a child opens its own confirm
   * dialog in a separate portal — Radix would otherwise treat that confirm
   * click as an outside click on the parent and dismiss it. Escape and the
   * close button still work.
   */
  preventOutsideClose?: boolean;
  /**
   * When set, the `title` is rendered as `sr-only` (accessibility only) and
   * this node is shown as the visible header content instead. Use to replace
   * the default large title with a custom layout (e.g. a small eyebrow label).
   * Pass `null` to suppress the visible header entirely while keeping the
   * title accessible.
   */
  headerContent?: ReactNode;
}

const sizeCls: Record<Size, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

/**
 * Centered modal built on Radix Dialog. Inherits `dir="rtl"` from `<html>`,
 * traps focus, and closes on Escape / overlay click. Used for both the
 * `<ConfirmDialog>` and entity detail modals in the per-page polish PRs.
 */
export default function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
  preventOutsideClose = false,
  headerContent,
}: DialogProps) {
  const { t } = useTranslation(['common', 'http']);
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" />
        <RadixDialog.Content
          // Suppress Radix's default auto-focus on the first focusable child.
          // It tends to land on a destructive button (delete) in detail
          // modals, which both reads as urgency and shows the red focus ring
          // immediately on open. Radix still focuses the Content wrapper for
          // screen readers; users tab from there.
          onOpenAutoFocus={(e) => e.preventDefault()}
          // When no `description` is provided we render no Radix Description
          // node; tell Radix that's intentional so it stops warning about a
          // missing `aria-describedby`.
          {...(description ? {} : { "aria-describedby": undefined })}
          onPointerDownOutside={
            preventOutsideClose ? (e) => e.preventDefault() : undefined
          }
          onInteractOutside={
            preventOutsideClose ? (e) => e.preventDefault() : undefined
          }
          className={[
            "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-1.5rem)] -translate-x-1/2 -translate-y-1/2 sm:w-[calc(100vw-2rem)]",
            "rounded-xl border border-white/8 bg-card-raised p-4 text-white/85 shadow-2xl shadow-black/60 sm:p-6",
            "max-h-[calc(100vh-1.5rem)] overflow-y-auto sm:max-h-[calc(100vh-2rem)]",
            sizeCls[size],
          ].join(" ")}
        >
          <div className="flex items-start justify-between gap-4">
            {headerContent !== undefined ? (
              <>
                <RadixDialog.Title className="sr-only">{title}</RadixDialog.Title>
                {description && (
                  <RadixDialog.Description className="sr-only">{description}</RadixDialog.Description>
                )}
                <div className="min-w-0 grow">{headerContent}</div>
              </>
            ) : (
              <div className="min-w-0">
                <RadixDialog.Title className="text-lg font-semibold text-white sm:text-xl">
                  {title}
                </RadixDialog.Title>
                {description && (
                  <RadixDialog.Description className="mt-1 text-sm text-white/60">
                    {description}
                  </RadixDialog.Description>
                )}
              </div>
            )}
            <RadixDialog.Close
              aria-label={t("common:close")}
              className="shrink-0 rounded-sm p-1 text-white/30 transition hover:bg-white/8 hover:text-white/70 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white/30"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-4" aria-hidden="true">
                <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
              </svg>
            </RadixDialog.Close>
          </div>
          {children && <div className="mt-4">{children}</div>}
          {footer && (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2 *:flex-1 *:whitespace-nowrap">{footer}</div>
          )}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

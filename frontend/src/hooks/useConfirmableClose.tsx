import { useState } from "react";

import { useTranslation } from "react-i18next";

import ConfirmDialog from "@/components/ui/ConfirmDialog";

interface UseConfirmableCloseArgs {
  isDirty: boolean;
  onClose: () => void;
}

interface UseConfirmableCloseResult {
  /** Call when the user requests close; opens the discard prompt if dirty. */
  handleClose: () => void;
  /** Render this in the JSX tree — the discard <ConfirmDialog>. */
  discardConfirm: React.ReactElement;
}

/**
 * Wraps the "are you sure you want to discard changes?" pattern. Callers
 * pass an `isDirty` boolean (callers own the comparison — JSON.stringify,
 * field check, etc.) and an `onClose` to fire after confirmation.
 */
export function useConfirmableClose({
  isDirty,
  onClose,
}: UseConfirmableCloseArgs): UseConfirmableCloseResult {
  const { t } = useTranslation('common');
  const [open, setOpen] = useState(false);

  function handleClose() {
    if (isDirty) {
      setOpen(true);
    } else {
      onClose();
    }
  }

  const discardConfirm = (
    <ConfirmDialog
      open={open}
      onOpenChange={(o) => !o && setOpen(false)}
      title={t("common:discardTitle")}
      message={t("common:discardMessage")}
      cancelLabel={t("common:continueEditing")}
      confirmLabel={t("common:discard")}
      variant="danger"
      onConfirm={() => {
        setOpen(false);
        onClose();
      }}
    />
  );

  return { handleClose, discardConfirm };
}

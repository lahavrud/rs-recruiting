import { useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import Dialog from "@/components/ui/Dialog";
import { useConfirmableClose } from "@/hooks/useConfirmableClose";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import { useToast } from "@/hooks/useToast";
import { adminCreateCompany } from "@/services/adminCompanies";
import type { CompanyProfileAdminCreate, CompanyProfileRead } from "@/types/api";
import { focusFirstError } from "@/utils/focusFirstError";
import {
  COMPANY_PROFILE_FIELD_ORDER,
  validateCompanyProfile,
} from "@/utils/validators";

import CompanyProfileFields from "./CompanyProfileFields";

interface CreateProps {
  open: boolean;
  onClose: () => void;
  onCreated: (profile: CompanyProfileRead) => void;
}

export default function CreateCompanyDialog({ open, onClose, onCreated }: CreateProps) {
  const { t } = useTranslation(['active', 'admin', 'common']);
  const toast = useToast();
  const [form, setForm] = useState<Partial<CompanyProfileAdminCreate>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [confirmCreateOpen, setConfirmCreateOpen] = useState(false);

  const isDirty = !saving && Object.values(form).some((v) => v != null && v !== "");
  const { handleClose: requestClose, discardConfirm } = useConfirmableClose({
    isDirty,
    onClose,
  });

  useResetOnTrigger(open, () => {
    setForm({});
    setErrors({});
    setConfirmCreateOpen(false);
  });

  function set<K extends keyof CompanyProfileAdminCreate>(
    key: K,
    value: CompanyProfileAdminCreate[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
    // Clear that field's error on edit.
    if (errors[key as string]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key as string];
        return next;
      });
    }
  }

  function validate(): boolean {
    const e = validateCompanyProfile(form, t);
    setErrors(e);
    if (Object.keys(e).length > 0) {
      focusFirstError(e, COMPANY_PROFILE_FIELD_ORDER);
      return false;
    }
    return true;
  }

  function requestSave() {
    if (!validate()) return;
    setConfirmCreateOpen(true);
  }

  async function executeSave() {
    setConfirmCreateOpen(false);
    setSaving(true);
    try {
      const created = await adminCreateCompany({
        name: form.name!,
        company_id: form.company_id!,
        address: form.address!,
        contact_email: form.contact_email!,
        contact_first_name: form.contact_first_name!,
        contact_last_name: form.contact_last_name!,
        contact_mobile_phone: form.contact_mobile_phone!,
        contact_landline_phone: form.contact_landline_phone || null,
      });
      toast.success(t("admin:companies.createdToast"));
      onCreated(created);
    } catch {
      toast.error(t("admin:companies.errors.createFailed"));
    } finally {
      setSaving(false);
    }
  }

  const hasErrors = Object.keys(errors).length > 0;

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(o) => { if (!o) requestClose(); }}
        title={t("admin:companies.newCompanyModalTitle")}
        description={t("admin:companies.newCompanyModalDescription")}
        size="lg"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={requestClose}
              disabled={saving}
            >
              {t("common:cancel")}
            </Button>
            <Button
              onClick={requestSave}
              disabled={saving}
              className="active:scale-95"
            >
              {saving ? t("common:saving") : t("admin:companies.createSubmit")}
            </Button>
          </>
        }
      >
        <CompanyProfileFields
          form={form}
          setField={(k, v) =>
            set(
              k as keyof CompanyProfileAdminCreate,
              v as CompanyProfileAdminCreate[keyof CompanyProfileAdminCreate],
            )
          }
          errors={errors}
          showRequired
        />
        {hasErrors && (
          <p className="mt-3 text-xs text-danger">
            {t("admin:companies.validation.fixErrors")}
          </p>
        )}
      </Dialog>
      <ConfirmDialog
        open={confirmCreateOpen}
        onOpenChange={(o) => !o && setConfirmCreateOpen(false)}
        title={t("admin:companies.createConfirmTitle")}
        message={t("admin:companies.createConfirmMessage", { name: form.name })}
        confirmLabel={t("admin:companies.createSubmit")}
        onConfirm={executeSave}
      />
      {discardConfirm}
    </>
  );
}

import { useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import { useConfirmableClose } from "@/hooks/useConfirmableClose";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import { useToast } from "@/hooks/useToast";
import { updateCompanyProfile } from "@/services/adminCompanies";
import type { CompanyProfileAdminUpdate, CompanyProfileRead } from "@/types/api";
import { focusFirstError } from "@/utils/focusFirstError";
import { isDirtyByJSON } from "@/utils/isDirty";
import {
  COMPANY_PROFILE_FIELD_ORDER,
  validateCompanyProfile,
} from "@/utils/validators";

import CompanyProfileFields from "./CompanyProfileFields";

interface EditProps {
  profile: CompanyProfileRead | null;
  onClose: () => void;
  onSaved: (next: CompanyProfileRead) => void;
}

function seedFromProfile(p: CompanyProfileRead): CompanyProfileAdminUpdate {
  return {
    name: p.name,
    company_id: p.company_id ?? "",
    address: p.address ?? "",
    contact_email: p.contact_email ?? "",
    contact_first_name: p.contact_first_name ?? "",
    contact_last_name: p.contact_last_name ?? "",
    contact_mobile_phone: p.contact_mobile_phone ?? "",
    contact_landline_phone: p.contact_landline_phone ?? "",
  };
}

export default function EditCompanyDialog({ profile, onClose, onSaved }: EditProps) {
  const { t } = useTranslation(['admin', 'common']);
  const toast = useToast();
  const [form, setForm] = useState<CompanyProfileAdminUpdate>({});
  const [initialForm, setInitialForm] = useState<CompanyProfileAdminUpdate>({});
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useResetOnTrigger(profile, () => {
    if (!profile) return;
    const seed = seedFromProfile(profile);
    setForm(seed);
    setInitialForm(seed);
    setErrors({});
  });

  function set<K extends keyof CompanyProfileAdminUpdate>(key: K, value: CompanyProfileAdminUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key as string]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key as string];
        return next;
      });
    }
  }

  const isDirty = isDirtyByJSON(form, initialForm);
  const { handleClose, discardConfirm } = useConfirmableClose({ isDirty, onClose });

  async function handleSave() {
    if (!profile) return;
    const e = validateCompanyProfile(form, t);
    setErrors(e);
    if (Object.keys(e).length > 0) {
      focusFirstError(e, COMPANY_PROFILE_FIELD_ORDER);
      return;
    }
    setSaving(true);
    try {
      const updated = await updateCompanyProfile(profile.id, {
        ...form,
        contact_landline_phone: form.contact_landline_phone || null,
      });
      onSaved(updated);
    } catch {
      toast.error(t("admin:companies.errors.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  if (!profile) return null;

  return (
    <>
      <Dialog
        open={profile != null}
        onOpenChange={(o) => !o && handleClose()}
        title={t("admin:companies.editModalTitle")}
        description={profile.name}
        size="lg"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={handleClose}
              disabled={saving}
            >
              {t("common:cancel")}
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? t("common:saving") : t("common:save")}
            </Button>
          </>
        }
      >
        <CompanyProfileFields
          form={form}
          setField={(k, v) =>
            set(
              k as keyof CompanyProfileAdminUpdate,
              v as CompanyProfileAdminUpdate[keyof CompanyProfileAdminUpdate],
            )
          }
          errors={errors}
        />
      </Dialog>
      {discardConfirm}
    </>
  );
}

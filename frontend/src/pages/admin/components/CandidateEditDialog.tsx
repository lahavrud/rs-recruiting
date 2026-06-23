import { useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Field from "@/components/ui/Field";
import { useConfirmableClose } from "@/hooks/useConfirmableClose";
import { useResetOnTrigger } from "@/hooks/useResetOnTrigger";
import { updateCandidate } from "@/services/adminCandidates";
import { INPUT_CLS } from "@/styles/forms";
import type { CandidateProfileRead, CandidateProfileUpdate } from "@/types/candidates";
import { isDirtyByJSON } from "@/utils/isDirty";
import { EMAIL_RE, MOBILE_RE } from "@/utils/validators";

interface EditProps {
  candidate: CandidateProfileRead | null;
  onClose: () => void;
  onSaved: (next: CandidateProfileRead) => void;
  onError: () => void;
}

export default function CandidateEditDialog({
  candidate,
  onClose,
  onSaved,
  onError,
}: EditProps) {
  const { t } = useTranslation(["admin", "common"]);
  const [form, setForm] = useState<CandidateProfileUpdate>({});
  const [initialForm, setInitialForm] = useState<CandidateProfileUpdate>({});
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useResetOnTrigger(candidate, () => {
    if (!candidate) return;
    const seed: CandidateProfileUpdate = {
      full_name: candidate.full_name,
      email: candidate.email,
      phone: candidate.phone ?? "",
      linkedin_url: candidate.linkedin_url ?? "",
    };
    setForm(seed);
    setInitialForm(seed);
    setErrors({});
  });

  function set<K extends keyof CandidateProfileUpdate>(
    key: K,
    value: CandidateProfileUpdate[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key as string]) setErrors((prev) => ({ ...prev, [key as string]: "" }));
  }

  const isDirty = isDirtyByJSON(form, initialForm);
  const { handleClose, discardConfirm } = useConfirmableClose({ isDirty, onClose });

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.full_name?.trim()) e.full_name = t("common:validation.required");
    else if (form.full_name.trim().length < 2)
      e.full_name = t("common:validation.tooShort", { min: 2 });
    else if (form.full_name.length > 100)
      e.full_name = t("common:validation.tooLong", { max: 100 });
    if (!form.email?.trim()) e.email = t("common:validation.required");
    else if (!EMAIL_RE.test(form.email)) e.email = t("common:validation.emailInvalid");
    if (!form.phone?.trim()) e.phone = t("common:validation.required");
    else if (!MOBILE_RE.test(form.phone.trim())) {
      e.phone = t("common:validation.phoneInvalid");
    }
    if (form.linkedin_url?.trim()) {
      try {
        const url = new URL(form.linkedin_url);
        if (!url.hostname.endsWith("linkedin.com"))
          e.linkedin_url = t("common:validation.linkedinInvalid");
      } catch {
        e.linkedin_url = t("common:validation.linkedinInvalid");
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSave() {
    if (!candidate || !validate()) return;
    setSaving(true);
    const body: CandidateProfileUpdate = {
      full_name: form.full_name,
      email: form.email,
      phone: form.phone,
      linkedin_url: form.linkedin_url?.trim() ? form.linkedin_url : null,
    };
    try {
      const updated = await updateCandidate(candidate.id, body);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  if (!candidate) return null;

  return (
    <>
      <Dialog
        open={candidate != null}
        onOpenChange={(o) => !o && handleClose()}
        title={t("admin:candidates.editModalTitle")}
        description={candidate.email}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={handleClose} disabled={saving}>
              {t("common:cancel")}
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? t("common:saving") : t("common:save")}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <Field label={t("admin:candidates.fields.fullName")} error={errors.full_name}>
            <input
              type="text"
              value={form.full_name ?? ""}
              onChange={(e) => set("full_name", e.target.value)}
              className={INPUT_CLS}
            />
          </Field>
          <Field label={t("admin:candidates.fields.email")} error={errors.email}>
            <input
              type="email"
              value={form.email ?? ""}
              onChange={(e) => set("email", e.target.value)}
              className={INPUT_CLS}
            />
          </Field>
          <Field label={t("admin:candidates.fields.phone")} error={errors.phone}>
            <input
              type="tel"
              value={form.phone ?? ""}
              onChange={(e) => set("phone", e.target.value)}
              className={INPUT_CLS}
            />
          </Field>
          <Field
            label={t("admin:candidates.fields.linkedin")}
            error={errors.linkedin_url}
          >
            <input
              type="url"
              value={form.linkedin_url ?? ""}
              onChange={(e) => set("linkedin_url", e.target.value)}
              className={INPUT_CLS}
            />
          </Field>
        </div>
      </Dialog>
      {discardConfirm}
    </>
  );
}

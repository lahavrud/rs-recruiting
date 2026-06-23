import { useEffect, useRef, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import Eyebrow from "@/components/ui/Eyebrow";
import { useToast } from "@/hooks/useToast";
import { createInvite } from "@/services/adminInvites";
import { inputCls } from "@/styles/forms";
import type { InviteTokenCreate, InviteTokenRead } from "@/types/api";

interface InviteFormProps {
  open: boolean;
  onClose: () => void;
  onCreated: (invite: InviteTokenRead) => void;
}

export default function InviteFormDialog({ open, onClose, onCreated }: InviteFormProps) {
  const { t } = useTranslation('admin');
  const toast = useToast();
  const [form, setForm] = useState<InviteTokenCreate>({ email: "" });
  const [submitting, setSubmitting] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm({ email: "" });
    setErrorKey(null);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [open]);

  async function handleSubmit() {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setErrorKey(null);
    setSubmitting(true);
    try {
      const created = await createInvite(form);
      toast.success(t("admin:companies.inviteForm.successMessage"));
      onCreated(created);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const detail = err.response.data?.detail ?? "";
        if (
          typeof detail === "string" &&
          detail.toLowerCase().includes("pending invite")
        ) {
          setErrorKey("admin:companies.inviteForm.errorPendingInvite");
        } else {
          setErrorKey("admin:companies.inviteForm.errorEmailExists");
        }
      } else {
        setErrorKey("admin:companies.inviteForm.errorMessage");
      }
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin:companies.inviteForm.title")}
      size="md"
      footer={
        <>
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={submitting}
          >
            {t("admin:companies.inviteForm.cancelButton")}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || !form.email}
          >
            {submitting
              ? t("admin:companies.inviteForm.submittingButton")
              : t("admin:companies.inviteForm.submitButton")}
          </Button>
        </>
      }
    >
      <InviteFlowExplainer />
      <label className="block text-sm">
        <span className="block text-xs text-white/45">
          {t("admin:companies.inviteForm.emailLabel")}
        </span>
        <input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ email: e.target.value })}
          className={`mt-1 ${inputCls}`}
          placeholder={t("admin:companies.inviteForm.emailPlaceholder")}
        />
      </label>
      {errorKey && <p className="mt-3 text-xs text-danger">{t(errorKey)}</p>}
    </Dialog>
  );
}

/** Short visual flow of what happens after the admin sends an invite. */
function InviteFlowExplainer() {
  const { t } = useTranslation('admin');
  const steps = [
    {
      label: t("admin:companies.inviteForm.flow.step1"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="size-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 7l9 6 9-6M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
        </svg>
      ),
    },
    {
      label: t("admin:companies.inviteForm.flow.step2"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="size-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm10-3v6m3-3h-6" />
        </svg>
      ),
    },
    {
      label: t("admin:companies.inviteForm.flow.step3"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="size-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 12l5 5L20 7" />
        </svg>
      ),
    },
    {
      label: t("admin:companies.inviteForm.flow.step4"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="size-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 11V7a4 4 0 1 0-8 0v4M5 11h14v8H5Z" />
        </svg>
      ),
    },
    {
      label: t("admin:companies.inviteForm.flow.step5"),
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="size-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2ZM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      ),
    },
  ];
  return (
    <div className="mb-5 rounded-md border border-white/8 bg-card/40 p-3">
      <Eyebrow className="mb-3">
        {t("admin:companies.inviteForm.flow.title")}
      </Eyebrow>
      {/* dir="ltr" so the step sequence renders left-to-right regardless of
          document direction. Hebrew labels inside each cell still render RTL
          naturally because the characters themselves carry direction. */}
      <ol dir="ltr" className="flex items-start gap-1">
        {steps.map((step, i) => (
          <li key={i} className="flex flex-1 items-start gap-1">
            <div className="flex flex-1 flex-col items-center text-center">
              <div className="flex size-7 items-center justify-center rounded-full border border-copper/35 bg-copper/10 text-copper">
                {step.icon}
              </div>
              <p className="mt-1.5 leading-tight text-[10px] text-white/65">
                {step.label}
              </p>
            </div>
            {i < steps.length - 1 && (
              <svg
                viewBox="0 0 16 16"
                fill="currentColor"
                className="mt-2.5 size-3 shrink-0 text-white/25"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06L7.28 11.78a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

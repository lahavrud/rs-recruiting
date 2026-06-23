import { type FormEvent, type RefObject } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import SignatureCanvas, { type SignatureCanvasRef } from "@/components/ui/SignatureCanvas";

interface FieldErrors {
  terms?: string;
  privacy?: string;
  signature?: string;
}

interface Props {
  isTermsAccepted: boolean;
  isPrivacyAccepted: boolean;
  fieldErrors: FieldErrors;
  isSubmitting: boolean;
  sigCanvasRef: RefObject<SignatureCanvasRef | null>;
  onTermsChange: (accepted: boolean) => void;
  onPrivacyChange: (accepted: boolean) => void;
  onSignatureBegin: () => void;
  onOpenContract: () => void;
  onOpenTerms: () => void;
  onOpenPrivacy: () => void;
  onBack: () => void;
  onSubmit: (e: FormEvent) => void;
}

export default function RegisterStep2Form({
  isTermsAccepted,
  isPrivacyAccepted,
  fieldErrors,
  isSubmitting,
  sigCanvasRef,
  onTermsChange,
  onPrivacyChange,
  onSignatureBegin,
  onOpenContract,
  onOpenTerms,
  onOpenPrivacy,
  onBack,
  onSubmit,
}: Props) {
  const { t } = useTranslation('auth');

  return (
    <form onSubmit={onSubmit} noValidate>
      <div className="space-y-4">
        <div className="space-y-3 rounded-xl border border-white/8 bg-card px-5 py-5">
          <Eyebrow>{t("auth:register.agreementSection")}</Eyebrow>

          {/* Service contract */}
          <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-white/60">
                {t("auth:register.agreementSectionService")}
              </p>
              <button
                type="button"
                onClick={onOpenContract}
                className="text-[11px] text-copper/70 transition hover:text-copper"
              >
                {t("auth:register.agreementReadFull")}
              </button>
            </div>
            <div className="mt-2 max-h-20 overflow-y-auto [scrollbar-width:thin]">
              <p className="text-xs leading-relaxed text-white/30">
                {t("auth:register.agreementTextService")}
              </p>
            </div>
          </div>

          {/* Site Terms of Service */}
          <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-white/60">
                {t("auth:register.agreementSectionSiteTerms")}
              </p>
              <button
                type="button"
                onClick={onOpenTerms}
                className="text-[11px] text-copper/70 transition hover:text-copper"
              >
                {t("auth:register.agreementReadFull")}
              </button>
            </div>
            <div className="mt-2 max-h-20 overflow-y-auto [scrollbar-width:thin]">
              <p className="text-xs leading-relaxed text-white/30">
                {t("auth:register.agreementTextSiteTermsPreview")}
              </p>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-2.5 text-sm text-white/60">
              <input
                type="checkbox"
                checked={isTermsAccepted}
                onChange={(e) => onTermsChange(e.target.checked)}
                className="accent-copper"
              />
              {t("auth:register.termsCheckboxLabel")}
            </label>
            {fieldErrors.terms && (
              <p className="mt-1 text-xs text-danger">{fieldErrors.terms}</p>
            )}
          </div>

          {/* Privacy policy */}
          <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-white/60">
                {t("auth:register.agreementSectionPrivacy")}
              </p>
              <button
                type="button"
                onClick={onOpenPrivacy}
                className="text-[11px] text-copper/70 transition hover:text-copper"
              >
                {t("auth:register.agreementReadFull")}
              </button>
            </div>
            <div className="mt-2 max-h-20 overflow-y-auto [scrollbar-width:thin]">
              <p className="text-xs leading-relaxed text-white/30">
                {t("auth:register.agreementTextPrivacyPreview")}
              </p>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-2.5 text-sm text-white/60">
              <input
                type="checkbox"
                checked={isPrivacyAccepted}
                onChange={(e) => onPrivacyChange(e.target.checked)}
                className="accent-copper"
              />
              {t("auth:register.privacyCheckboxLabel")}
            </label>
            {fieldErrors.privacy && (
              <p className="mt-1 text-xs text-danger">{fieldErrors.privacy}</p>
            )}
          </div>

          {/* Signature */}
          <div>
            <p className="mb-2 text-xs text-white/45">
              {t("auth:register.signatureLabel")}{" "}
              <span className="text-copper/60">*</span>
            </p>
            <SignatureCanvas
              ref={sigCanvasRef}
              hasError={!!fieldErrors.signature}
              onBegin={onSignatureBegin}
            />
            {fieldErrors.signature && (
              <p className="mt-1 text-xs text-danger">{fieldErrors.signature}</p>
            )}
          </div>
        </div>

        <div className="flex gap-3">
          <Button
            type="button"
            variant="ghost"
            size="lg"
            onClick={onBack}
            className="flex-1"
          >
            → {t("auth:register.backStep")}
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting}
            size="lg"
            className="flex-[2]"
          >
            {isSubmitting ? t("auth:register.submittingText") : t("auth:register.submitText")}
          </Button>
        </div>
      </div>
    </form>
  );
}

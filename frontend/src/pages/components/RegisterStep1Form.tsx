import { type ChangeEvent, type RefObject } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import Field from "@/components/ui/Field";
import { INPUT_CLS } from "@/styles/forms";

interface FormState {
  email: string;
  password: string;
  confirm: string;
  companyName: string;
  companyId: string;
  address: string;
  contactFirstName: string;
  contactLastName: string;
  contactMobilePhone: string;
  contactLandlinePhone: string;
}

type FieldErrors = Partial<
  FormState & { logo: string; signature: string; privacy: string; terms: string }
>;

interface Props {
  form: FormState;
  fieldErrors: FieldErrors;
  isEmailPreFilled: boolean;
  logoInputRef: RefObject<HTMLInputElement | null>;
  onFieldChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onFieldBlur: (e: ChangeEvent<HTMLInputElement>) => void;
  onLogoChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onNext: () => void;
}

export default function RegisterStep1Form({
  form,
  fieldErrors,
  isEmailPreFilled,
  logoInputRef,
  onFieldChange,
  onFieldBlur,
  onLogoChange,
  onNext,
}: Props) {
  const { t } = useTranslation('auth');

  return (
    <div className="space-y-4">
      {/* Company details */}
      <div className="rounded-xl border border-white/8 bg-card px-5 py-5">
        <Eyebrow className="mb-4">{t("auth:register.companySection")}</Eyebrow>
        <div className="space-y-3">
          <Field label={`${t("auth:register.companyName")} *`} error={fieldErrors.companyName}>
            <input
              name="companyName"
              type="text"
              required
              maxLength={100}
              value={form.companyName}
              onChange={onFieldChange}
              onBlur={onFieldBlur}
              className={INPUT_CLS}
              placeholder="Acme בע״מ"
              autoComplete="organization"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={`${t("auth:register.companyIdLabel")} *`} error={fieldErrors.companyId}>
              <input
                name="companyId"
                type="text"
                required
                maxLength={9}
                value={form.companyId}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder="123456789"
                dir="ltr"
              />
            </Field>
            <Field label={`${t("auth:register.addressLabel")} *`} error={fieldErrors.address}>
              <input
                name="address"
                type="text"
                required
                maxLength={200}
                value={form.address}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder={t("auth:register.addressPlaceholder")}
                autoComplete="street-address"
              />
            </Field>
          </div>

          <Field label={`${t("auth:register.logoLabel")} *`} error={fieldErrors.logo}>
            <input
              ref={logoInputRef}
              type="file"
              accept="image/*"
              onChange={onLogoChange}
              className="mt-0.5 block w-full cursor-pointer rounded-sm border border-white/10 bg-well px-3 py-2 text-xs text-white/50 file:ml-3 file:rounded-sm file:border-0 file:bg-copper/20 file:px-2.5 file:py-1 file:text-[11px] file:font-medium file:text-copper hover:file:bg-copper/30"
            />
          </Field>
        </div>
      </div>

      {/* Contact details */}
      <div className="rounded-xl border border-white/8 bg-card px-5 py-5">
        <Eyebrow className="mb-4">
          {t("auth:register.contactSection", "איש קשר")}
        </Eyebrow>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={`${t("auth:register.contactFirstName")} *`}
              error={fieldErrors.contactFirstName}
            >
              <input
                name="contactFirstName"
                type="text"
                required
                maxLength={100}
                value={form.contactFirstName}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder={t("auth:register.contactFirstNamePlaceholder")}
                autoComplete="given-name"
              />
            </Field>
            <Field
              label={`${t("auth:register.contactLastName")} *`}
              error={fieldErrors.contactLastName}
            >
              <input
                name="contactLastName"
                type="text"
                required
                maxLength={100}
                value={form.contactLastName}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder={t("auth:register.contactLastNamePlaceholder")}
                autoComplete="family-name"
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={`${t("auth:register.contactMobilePhone")} *`}
              error={fieldErrors.contactMobilePhone}
            >
              <input
                name="contactMobilePhone"
                type="tel"
                required
                maxLength={15}
                value={form.contactMobilePhone}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder={t("auth:register.contactMobilePhonePlaceholder")}
                autoComplete="tel"
                dir="ltr"
              />
            </Field>
            <Field label={t("auth:register.contactLandlinePhone")}>
              <input
                name="contactLandlinePhone"
                type="tel"
                maxLength={15}
                value={form.contactLandlinePhone}
                onChange={onFieldChange}
                className={INPUT_CLS}
                placeholder={t("auth:register.contactLandlinePhonePlaceholder")}
                dir="ltr"
              />
            </Field>
          </div>
        </div>
      </div>

      {/* Account credentials */}
      <div className="rounded-xl border border-white/8 bg-card px-5 py-5">
        <Eyebrow className="mb-4">{t("auth:register.accountSection")}</Eyebrow>
        <div className="space-y-3">
          <Field label={`${t("auth:register.emailLabel")} *`} error={fieldErrors.email}>
            <input
              name="email"
              type="email"
              required
              maxLength={255}
              value={form.email}
              onChange={onFieldChange}
              onBlur={onFieldBlur}
              readOnly={isEmailPreFilled}
              className={`${INPUT_CLS} ${isEmailPreFilled ? "cursor-not-allowed opacity-60" : ""}`}
              placeholder={t("auth:register.emailPlaceholder")}
              autoComplete="email"
              dir="ltr"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={`${t("auth:register.passwordLabel")} *`} error={fieldErrors.password}>
              <input
                name="password"
                type="password"
                required
                value={form.password}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </Field>
            <Field label={`${t("auth:register.confirmLabel")} *`} error={fieldErrors.confirm}>
              <input
                name="confirm"
                type="password"
                required
                value={form.confirm}
                onChange={onFieldChange}
                onBlur={onFieldBlur}
                className={INPUT_CLS}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </Field>
          </div>
        </div>
      </div>

      <Button type="button" onClick={onNext} className="w-full py-2.5">
        {t("auth:register.nextStep")} ←
      </Button>
    </div>
  );
}

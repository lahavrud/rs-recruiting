import { useTranslation } from "react-i18next";

import Eyebrow from "@/components/ui/Eyebrow";
import Field from "@/components/ui/Field";
import { inputCls } from "@/styles/forms";
import type {
  CompanyProfileAdminCreate,
  CompanyProfileAdminUpdate,
} from "@/types/api";

interface ProfileFieldsProps {
  form: CompanyProfileAdminUpdate | Partial<CompanyProfileAdminCreate>;
  setField: (key: string, value: string) => void;
  errors?: Record<string, string>;
  /** If true, mark required fields with an asterisk and show inline hints. */
  showRequired?: boolean;
}

export default function CompanyProfileFields({
  form,
  setField,
  errors,
  showRequired = false,
}: ProfileFieldsProps) {
  const { t } = useTranslation('admin');
  return (
    <div className="space-y-5">
      {/* Section: Company */}
      <section>
        <Eyebrow className="mb-3">
          {t("admin:companies.formSections.company")}
        </Eyebrow>
        <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <Field
            label={t("admin:companies.fields.name")}
            required={showRequired}
            full
            name="name"
            error={errors?.name}
          >
            <input
              type="text"
              value={form.name ?? ""}
              onChange={(e) => setField("name", e.target.value)}
              className={inputCls}
              placeholder={t("admin:companies.placeholders.name")}
              aria-invalid={!!errors?.name}
            />
          </Field>
          <Field
            label={t("admin:companies.fields.companyId")}
            required={showRequired}
            hint={showRequired ? t("admin:companies.hints.companyId") : undefined}
            name="company_id"
            error={errors?.company_id}
          >
            <input
              type="text"
              inputMode="numeric"
              value={form.company_id ?? ""}
              onChange={(e) => setField("company_id", e.target.value)}
              className={inputCls}
              placeholder="123456789"
              aria-invalid={!!errors?.company_id}
              maxLength={9}
            />
          </Field>
          <Field
            label={t("admin:companies.fields.address")}
            required={showRequired}
            name="address"
            error={errors?.address}
          >
            <input
              type="text"
              value={form.address ?? ""}
              onChange={(e) => setField("address", e.target.value)}
              className={inputCls}
              placeholder={t("admin:companies.placeholders.address")}
              aria-invalid={!!errors?.address}
            />
          </Field>
        </div>
      </section>

      {/* Section: Contact person */}
      <section>
        <Eyebrow className="mb-3">
          {t("admin:companies.formSections.contact")}
        </Eyebrow>
        <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <Field
            label={t("admin:companies.fields.contactEmail")}
            required={showRequired}
            full
            name="contact_email"
            error={errors?.contact_email}
          >
            <input
              type="email"
              value={form.contact_email ?? ""}
              onChange={(e) => setField("contact_email", e.target.value)}
              className={inputCls}
              placeholder="contact@example.com"
              autoComplete="email"
              aria-invalid={!!errors?.contact_email}
            />
          </Field>
          <Field
            label={t("admin:companies.fields.contactFirstName")}
            required={showRequired}
            name="contact_first_name"
            error={errors?.contact_first_name}
          >
            <input
              type="text"
              value={form.contact_first_name ?? ""}
              onChange={(e) => setField("contact_first_name", e.target.value)}
              className={inputCls}
              autoComplete="given-name"
              aria-invalid={!!errors?.contact_first_name}
            />
          </Field>
          <Field
            label={t("admin:companies.fields.contactLastName")}
            required={showRequired}
            name="contact_last_name"
            error={errors?.contact_last_name}
          >
            <input
              type="text"
              value={form.contact_last_name ?? ""}
              onChange={(e) => setField("contact_last_name", e.target.value)}
              className={inputCls}
              autoComplete="family-name"
              aria-invalid={!!errors?.contact_last_name}
            />
          </Field>
          <Field
            label={t("admin:companies.fields.contactMobile")}
            required={showRequired}
            hint={showRequired ? t("admin:companies.hints.mobile") : undefined}
            name="contact_mobile_phone"
            error={errors?.contact_mobile_phone}
          >
            <input
              type="tel"
              value={form.contact_mobile_phone ?? ""}
              onChange={(e) => setField("contact_mobile_phone", e.target.value)}
              className={inputCls}
              placeholder="0501234567"
              autoComplete="tel"
              aria-invalid={!!errors?.contact_mobile_phone}
              maxLength={10}
            />
          </Field>
          <Field
            label={t("admin:companies.fields.contactLandline")}
            optional
          >
            <input
              type="tel"
              value={form.contact_landline_phone ?? ""}
              onChange={(e) => setField("contact_landline_phone", e.target.value)}
              className={inputCls}
              placeholder="03-1234567"
              autoComplete="tel"
            />
          </Field>
        </div>
      </section>
    </div>
  );
}

import { type FormEvent, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import PageHeader from "@/components/ui/PageHeader";
import { getMyCompanyProfile, updateMyCompanyProfile } from "@/services/companyProfile";
import { INPUT_CLS } from "@/styles/forms";
import type { CompanyProfileRead, CompanyProfileSelfUpdate } from "@/types/companies";
import { MOBILE_RE } from "@/utils/validators";

export default function CompanyProfilePage() {
  const { t } = useTranslation("company");
  const [profile, setProfile] = useState<CompanyProfileRead | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [contactFirstName, setContactFirstName] = useState("");
  const [contactLastName, setContactLastName] = useState("");
  const [contactMobile, setContactMobile] = useState("");
  const [contactLandline, setContactLandline] = useState("");
  const [mobileError, setMobileError] = useState<string | null>(null);

  useEffect(() => {
    getMyCompanyProfile()
      .then((p) => {
        setProfile(p);
        setName(p.name);
        setAddress(p.address);
        setContactFirstName(p.contact_first_name);
        setContactLastName(p.contact_last_name);
        setContactMobile(p.contact_mobile_phone);
        setContactLandline(p.contact_landline_phone ?? "");
      })
      .catch(() => setLoadError(true));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setMobileError(null);
    setSaveError(null);
    setSaveSuccess(false);

    if (!MOBILE_RE.test(contactMobile)) {
      setMobileError(t("company:profile.errors.invalidMobile"));
      return;
    }

    const update: CompanyProfileSelfUpdate = {
      name,
      address,
      contact_first_name: contactFirstName,
      contact_last_name: contactLastName,
      contact_mobile_phone: contactMobile,
      contact_landline_phone: contactLandline || null,
    };

    setIsSaving(true);
    try {
      const updated = await updateMyCompanyProfile(update);
      setProfile(updated);
      setSaveSuccess(true);
    } catch {
      setSaveError(t("company:profile.errors.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  if (loadError) {
    return (
      <div>
        <PageHeader eyebrow={t("company:profile.title")} />
        <p className="mt-4 text-sm text-danger">{t("company:profile.errors.loadFailed")}</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div>
        <PageHeader eyebrow={t("company:profile.title")} />
        <div className="mt-8 space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-lg bg-card" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("company:profile.title")}
        subtitle={t("company:profile.subtitle")}
      />

      <form onSubmit={handleSubmit} className="mt-6 max-w-2xl space-y-8">
        {/* Company details */}
        <section className="rounded-xl border border-white/8 bg-card p-6 space-y-4">
          <Eyebrow>{t("company:profile.section.company")}</Eyebrow>

          <div>
            <label htmlFor="cp-name" className="block text-sm text-white/50">
              {t("company:profile.fields.name")} <span className="text-copper/80">*</span>
            </label>
            <input
              id="cp-name"
              type="text"
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={`mt-1 ${INPUT_CLS}`}
            />
          </div>

          <div>
            <label className="block text-sm text-white/50">
              {t("company:profile.fields.companyId")}
            </label>
            <input
              type="text"
              readOnly
              value={profile.company_id}
              className={`mt-1 ${INPUT_CLS} cursor-not-allowed opacity-50`}
            />
            <p className="mt-1 text-xs text-white/30">{t("company:profile.readonly.companyIdNote")}</p>
          </div>

          <div>
            <label htmlFor="cp-address" className="block text-sm text-white/50">
              {t("company:profile.fields.address")} <span className="text-copper/80">*</span>
            </label>
            <input
              id="cp-address"
              type="text"
              required
              maxLength={200}
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className={`mt-1 ${INPUT_CLS}`}
              placeholder={t("company:profile.placeholders.address")}
            />
          </div>
        </section>

        {/* Contact person */}
        <section className="rounded-xl border border-white/8 bg-card p-6 space-y-4">
          <Eyebrow>{t("company:profile.section.contact")}</Eyebrow>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="cp-first" className="block text-sm text-white/50">
                {t("company:profile.fields.contactFirstName")} <span className="text-copper/80">*</span>
              </label>
              <input
                id="cp-first"
                type="text"
                required
                minLength={2}
                maxLength={100}
                value={contactFirstName}
                onChange={(e) => setContactFirstName(e.target.value)}
                className={`mt-1 ${INPUT_CLS}`}
              />
            </div>

            <div>
              <label htmlFor="cp-last" className="block text-sm text-white/50">
                {t("company:profile.fields.contactLastName")} <span className="text-copper/80">*</span>
              </label>
              <input
                id="cp-last"
                type="text"
                required
                minLength={2}
                maxLength={100}
                value={contactLastName}
                onChange={(e) => setContactLastName(e.target.value)}
                className={`mt-1 ${INPUT_CLS}`}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-white/50">
              {t("company:profile.fields.contactEmail")}
            </label>
            <input
              type="email"
              readOnly
              value={profile.contact_email}
              className={`mt-1 ${INPUT_CLS} cursor-not-allowed opacity-50`}
            />
            <p className="mt-1 text-xs text-white/30">{t("company:profile.readonly.emailNote")}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="cp-mobile" className="block text-sm text-white/50">
                {t("company:profile.fields.contactMobile")} <span className="text-copper/80">*</span>
              </label>
              <input
                id="cp-mobile"
                type="tel"
                required
                value={contactMobile}
                onChange={(e) => {
                  setContactMobile(e.target.value);
                  setMobileError(null);
                }}
                className={`mt-1 ${INPUT_CLS}${mobileError ? " border-danger/60" : ""}`}
                dir="ltr"
              />
              {mobileError && (
                <p className="mt-1 text-xs text-danger">{mobileError}</p>
              )}
            </div>

            <div>
              <label htmlFor="cp-landline" className="block text-sm text-white/50">
                {t("company:profile.fields.contactLandline")}
              </label>
              <input
                id="cp-landline"
                type="tel"
                maxLength={20}
                value={contactLandline}
                onChange={(e) => setContactLandline(e.target.value)}
                className={`mt-1 ${INPUT_CLS}`}
                placeholder={t("company:profile.placeholders.contactLandline")}
                dir="ltr"
              />
            </div>
          </div>
        </section>

        {saveSuccess && (
          <p className="text-sm text-success">{t("company:profile.saved")}</p>
        )}
        {saveError && (
          <p className="text-sm text-danger">{saveError}</p>
        )}

        <div className="flex justify-end">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? t("company:profile.saving") : t("company:profile.save")}
          </Button>
        </div>
      </form>
    </div>
  );
}

import { type FormEvent, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import Field from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { getMyCompanyProfile, updateMyCompanyProfile } from "@/services/companyProfile";
import { INPUT_CLS, errorAlertCls } from "@/styles/forms";
import type { CompanyProfileRead, CompanyProfileSelfUpdate } from "@/types/companies";
import { MOBILE_RE } from "@/utils/validators";

// ─── Sub-components ───────────────────────────────────────────────────────────

function CompanyAvatar({ name }: { name: string }) {
  const initial = name.trim()[0]?.toUpperCase() ?? "?";
  return (
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-copper/15 text-xl font-bold text-copper">
      {initial}
    </div>
  );
}

function ReadonlyValue({ value, ltr }: { value: string; ltr?: boolean }) {
  return (
    <div className="rounded-sm border border-white/6 bg-void px-3 py-2.5">
      <span className="text-sm text-white/45 select-all" dir={ltr ? "ltr" : undefined}>
        {value}
      </span>
    </div>
  );
}

function SkeletonCard({ rows }: { rows: number }) {
  return (
    <div className="rounded-xl border border-white/8 bg-card p-6">
      <div className="mb-5 h-3 w-20 animate-pulse rounded bg-white/10" />
      <div className="space-y-5">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-3 w-24 animate-pulse rounded bg-white/8" />
            <div className="h-10 animate-pulse rounded-sm bg-white/5" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

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
    let cancelled = false;
    getMyCompanyProfile()
      .then((p) => {
        if (cancelled) return;
        setProfile(p);
        setName(p.name);
        setAddress(p.address);
        setContactFirstName(p.contact_first_name);
        setContactLastName(p.contact_last_name);
        setContactMobile(p.contact_mobile_phone);
        setContactLandline(p.contact_landline_phone ?? "");
      })
      .catch(() => { if (!cancelled) setLoadError(true); });
    return () => { cancelled = true; };
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
      setName(updated.name);
      setAddress(updated.address);
      setContactFirstName(updated.contact_first_name);
      setContactLastName(updated.contact_last_name);
      setContactMobile(updated.contact_mobile_phone);
      setContactLandline(updated.contact_landline_phone ?? "");
      setSaveSuccess(true);
    } catch {
      setSaveError(t("company:profile.errors.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader eyebrow={t("company:profile.title")} />
        <p className="mt-4 text-sm text-danger">{t("company:profile.errors.loadFailed")}</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader eyebrow={t("company:profile.title")} />
        <div className="mt-6 space-y-4">
          {/* Identity header skeleton */}
          <div className="flex items-center gap-4 rounded-xl border border-white/8 bg-card p-6">
            <div className="h-14 w-14 animate-pulse rounded-full bg-white/8" />
            <div className="space-y-2">
              <div className="h-3 w-16 animate-pulse rounded bg-white/10" />
              <div className="h-5 w-40 animate-pulse rounded bg-white/8" />
              <div className="h-3 w-24 animate-pulse rounded bg-white/5" />
            </div>
          </div>
          <SkeletonCard rows={2} />
          <SkeletonCard rows={4} />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        eyebrow={t("company:profile.title")}
        subtitle={t("company:profile.subtitle")}
      />

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        {/* Identity header */}
        <div className="flex items-center gap-4 rounded-xl border border-white/8 bg-card p-5">
          <CompanyAvatar name={profile.name} />
          <div className="min-w-0">
            <Eyebrow className="mb-1">{t("company:profile.section.company")}</Eyebrow>
            <p className="truncate text-lg font-semibold text-white/90">{profile.name}</p>
            <p className="mt-0.5 text-xs text-white/35" dir="ltr">{profile.company_id}</p>
          </div>
        </div>

        {/* Company details */}
        <section className="rounded-xl border border-white/8 bg-card p-6">
          <Eyebrow className="mb-5">{t("company:profile.section.editDetails")}</Eyebrow>
          <div className="space-y-4">
            <Field
              id="cp-name"
              label={t("company:profile.fields.name")}
              required
            >
              <input
                id="cp-name"
                type="text"
                required
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={INPUT_CLS}
              />
            </Field>

            <Field
              label={t("company:profile.fields.companyId")}
              hint={t("company:profile.readonly.companyIdNote")}
            >
              <ReadonlyValue value={profile.company_id} ltr />
            </Field>

            <Field
              id="cp-address"
              label={t("company:profile.fields.address")}
              required
            >
              <input
                id="cp-address"
                type="text"
                required
                maxLength={200}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className={INPUT_CLS}
                placeholder={t("company:profile.placeholders.address")}
              />
            </Field>
          </div>
        </section>

        {/* Contact person */}
        <section className="rounded-xl border border-white/8 bg-card p-6">
          <Eyebrow className="mb-5">{t("company:profile.section.contact")}</Eyebrow>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="cp-first"
                label={t("company:profile.fields.contactFirstName")}
                required
              >
                <input
                  id="cp-first"
                  type="text"
                  required
                  minLength={2}
                  maxLength={100}
                  value={contactFirstName}
                  onChange={(e) => setContactFirstName(e.target.value)}
                  className={INPUT_CLS}
                />
              </Field>

              <Field
                id="cp-last"
                label={t("company:profile.fields.contactLastName")}
                required
              >
                <input
                  id="cp-last"
                  type="text"
                  required
                  minLength={2}
                  maxLength={100}
                  value={contactLastName}
                  onChange={(e) => setContactLastName(e.target.value)}
                  className={INPUT_CLS}
                />
              </Field>
            </div>

            <Field
              label={t("company:profile.fields.contactEmail")}
              hint={t("company:profile.readonly.emailNote")}
            >
              <ReadonlyValue value={profile.contact_email} ltr />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="cp-mobile"
                label={t("company:profile.fields.contactMobile")}
                required
                error={mobileError ?? undefined}
              >
                <input
                  id="cp-mobile"
                  type="tel"
                  required
                  value={contactMobile}
                  onChange={(e) => {
                    setContactMobile(e.target.value);
                    setMobileError(null);
                  }}
                  className={`${INPUT_CLS}${mobileError ? " border-danger/60" : ""}`}
                  dir="ltr"
                />
              </Field>

              <Field
                id="cp-landline"
                label={t("company:profile.fields.contactLandline")}
                optional
              >
                <input
                  id="cp-landline"
                  type="tel"
                  maxLength={20}
                  value={contactLandline}
                  onChange={(e) => setContactLandline(e.target.value)}
                  className={INPUT_CLS}
                  dir="ltr"
                />
              </Field>
            </div>
          </div>
        </section>

        {saveSuccess && (
          <div className="rounded-lg border border-success/20 bg-success/10 px-4 py-3 text-sm text-success">
            {t("company:profile.saved")}
          </div>
        )}
        {saveError && (
          <div className={errorAlertCls}>{saveError}</div>
        )}

        <div className="flex justify-end pb-2">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? t("company:profile.saving") : t("company:profile.save")}
          </Button>
        </div>
      </form>
    </div>
  );
}

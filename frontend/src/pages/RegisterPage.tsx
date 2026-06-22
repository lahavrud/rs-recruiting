import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useSearchParams } from "react-router-dom";

import Logo from "@/components/ui/Logo";
import { type SignatureCanvasRef } from "@/components/ui/SignatureCanvas";
import { useAuth } from "@/hooks/useAuth";
import { getInviteMetadata, register } from "@/services/auth";
import { errorAlertCls } from "@/styles/forms";

import AuthShell from "./components/AuthShell";
import RegisterModals from "./components/RegisterModals";
import RegisterStep1Form from "./components/RegisterStep1Form";
import RegisterStep2Form from "./components/RegisterStep2Form";

function useValidation() {
  const { t } = useTranslation(['auth', 'common']);
  return {
    validateEmail(v: string): string {
      if (!v.trim()) return t("auth:register.validation.emailRequired");
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v))
        return t("auth:register.validation.emailInvalid");
      return "";
    },
    validatePassword(v: string): string {
      if (!v) return t("auth:register.validation.passwordRequired");
      if (v.length < 8) return t("auth:register.validation.passwordMin");
      if (!/[A-Z]/.test(v)) return t("auth:register.validation.passwordUppercase");
      if (!/[a-z]/.test(v)) return t("auth:register.validation.passwordLowercase");
      if (!/\d/.test(v)) return t("auth:register.validation.passwordDigit");
      if (!/[^A-Za-z0-9]/.test(v)) return t("auth:register.validation.passwordSpecial");
      return "";
    },
    validateConfirm(v: string, pw: string): string {
      if (!v) return t("auth:register.validation.confirmRequired");
      if (v !== pw) return t("auth:register.validation.confirmMismatch");
      return "";
    },
    validateCompanyName(v: string): string {
      if (!v.trim()) return t("auth:register.validation.companyNameRequired");
      if (v.length > 100) return t("auth:register.validation.companyNameMax");
      return "";
    },
    validateCompanyId(v: string): string {
      if (!v.trim()) return t("auth:register.validation.companyIdRequired");
      if (!/^\d{9}$/.test(v)) return t("auth:register.validation.companyIdInvalid");
      return "";
    },
    validateContactFirstName(v: string): string {
      if (!v.trim()) return t("auth:register.validation.contactFirstNameRequired");
      return "";
    },
    validateContactLastName(v: string): string {
      if (!v.trim()) return t("auth:register.validation.contactLastNameRequired");
      return "";
    },
    validateMobilePhone(v: string): string {
      if (!v.trim()) return t("auth:register.validation.mobilePhoneRequired");
      if (!/^05[0-9]\d{7}$/.test(v.replace(/[-\s]/g, "")))
        return t("auth:register.validation.mobilePhoneInvalid");
      return "";
    },
    validateLogo(f: File | null): string {
      if (!f) return t("auth:register.validation.logoRequired");
      return "";
    },
    validateSignature(isEmpty: boolean): string {
      if (isEmpty) return t("auth:register.validation.signatureRequired");
      return "";
    },
    validateAddress(v: string): string {
      if (!v.trim()) return t("auth:register.validation.addressRequired");
      if (v.length > 200) return t("auth:register.validation.addressMax");
      return "";
    },
    validatePrivacy(accepted: boolean): string {
      if (!accepted) return t("auth:register.validation.privacyRequired");
      return "";
    },
    validateTerms(accepted: boolean): string {
      if (!accepted) return t("auth:register.validation.termsRequired");
      return "";
    },
  };
}

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

const EMPTY: FormState = {
  email: "",
  password: "",
  confirm: "",
  companyName: "",
  companyId: "",
  address: "",
  contactFirstName: "",
  contactLastName: "",
  contactMobilePhone: "",
  contactLandlinePhone: "",
};

export default function RegisterPage() {
  const { t } = useTranslation(['auth', 'common']);
  const val = useValidation();
  const { isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("token");

  const [step, setStep] = useState<1 | 2>(1);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<
    Partial<FormState & { logo: string; signature: string; privacy: string; terms: string }>
  >({});
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [contractOpen, setContractOpen] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(() => !!inviteToken);
  const [tokenInvalid, setTokenInvalid] = useState(false);
  const [emailPreFilled, setEmailPreFilled] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const sigCanvasRef = useRef<SignatureCanvasRef>(null);

  useEffect(() => {
    if (!inviteToken) return;
    getInviteMetadata(inviteToken)
      .then((meta) => {
        setForm((prev) => ({ ...prev, email: meta.email ?? prev.email }));
        if (meta.email) setEmailPreFilled(true);
      })
      .catch(() => setTokenInvalid(true))
      .finally(() => setMetadataLoading(false));
  }, [inviteToken]);

  useEffect(() => {
    if (contractOpen || termsOpen || privacyOpen)
      document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [contractOpen, termsOpen, privacyOpen]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  if (!inviteToken || tokenInvalid) {
    return (
      <AuthShell className="px-4">
        <div className="w-full max-w-md rounded-xl border border-white/10 bg-card p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-warning/30 bg-warning/10 text-lg text-warning">
            ✕
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth:register.noToken.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth:register.noToken.message")}
          </p>
          <Link
            to="/login"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("auth:register.noToken.backToLogin")}
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (metadataLoading) {
    return (
      <AuthShell className="">
        <p className="text-sm text-white/30">{t("common:loading")}</p>
      </AuthShell>
    );
  }

  function set(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    set(e.target.name as keyof FormState, e.target.value);
  }

  function handleBlur(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    let err = "";
    switch (name as keyof FormState) {
      case "email": err = val.validateEmail(value); break;
      case "password": err = val.validatePassword(value); break;
      case "confirm": err = val.validateConfirm(value, form.password); break;
      case "companyName": err = val.validateCompanyName(value); break;
      case "companyId": err = val.validateCompanyId(value); break;
      case "address": err = val.validateAddress(value); break;
      case "contactFirstName": err = val.validateContactFirstName(value); break;
      case "contactLastName": err = val.validateContactLastName(value); break;
      case "contactMobilePhone": err = val.validateMobilePhone(value); break;
    }
    setFieldErrors((prev) => ({ ...prev, [name]: err }));
  }

  function handleLogoChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setLogoFile(file);
    if (file) setFieldErrors((prev) => ({ ...prev, logo: "" }));
  }

  function validateStep1(): boolean {
    const errors: Partial<FormState & { logo: string }> = {
      companyName: val.validateCompanyName(form.companyName),
      companyId: val.validateCompanyId(form.companyId),
      address: val.validateAddress(form.address),
      contactFirstName: val.validateContactFirstName(form.contactFirstName),
      contactLastName: val.validateContactLastName(form.contactLastName),
      contactMobilePhone: val.validateMobilePhone(form.contactMobilePhone),
      email: val.validateEmail(form.email),
      password: val.validatePassword(form.password),
      confirm: val.validateConfirm(form.confirm, form.password),
      logo: val.validateLogo(logoFile),
    };
    setFieldErrors(errors);
    return Object.values(errors).every((e) => !e);
  }

  function validateStep2(): boolean {
    const errors = {
      signature: val.validateSignature(sigCanvasRef.current?.isEmpty() ?? true),
      terms: val.validateTerms(termsAccepted),
      privacy: val.validatePrivacy(privacyAccepted),
    };
    setFieldErrors((prev) => ({ ...prev, ...errors }));
    return Object.values(errors).every((e) => !e);
  }

  function handleNext() {
    if (validateStep1()) {
      setSubmitError(null);
      setStep(2);
      window.scrollTo(0, 0);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validateStep2()) return;

    const dataUrl = sigCanvasRef.current!.toDataURL();
    const sigBase64 = dataUrl.split(",")[1] ?? "";

    const fd = new FormData();
    fd.append("email", form.email.trim());
    fd.append("password", form.password);
    fd.append("company_name", form.companyName.trim());
    fd.append("company_id", form.companyId.trim());
    fd.append("address", form.address.trim());
    fd.append("contact_first_name", form.contactFirstName.trim());
    fd.append("contact_last_name", form.contactLastName.trim());
    fd.append("contact_mobile_phone", form.contactMobilePhone.trim());
    if (form.contactLandlinePhone.trim())
      fd.append("contact_landline_phone", form.contactLandlinePhone.trim());
    fd.append("agreement_signature", sigBase64);
    fd.append("privacy_accepted", String(privacyAccepted));
    fd.append("terms_accepted", String(termsAccepted));
    fd.append("logo", logoFile!);

    setSubmitting(true);
    setSubmitError(null);
    try {
      await register(fd, inviteToken!);
      setSuccess(true);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 422) {
          const detail = err.response?.data?.detail;
          const errors = Array.isArray(detail) ? detail : [];
          const pwErr = errors.find((e: { loc?: string[] }) => e.loc?.includes("password"));
          if (pwErr)
            setFieldErrors((prev) => ({
              ...prev,
              password: t("auth:register.validation.passwordComplexity"),
            }));
          else setSubmitError(t("auth:register.errors.failed"));
        } else if (status === 429) {
          setSubmitError(t("auth:register.errors.tooManyAttempts"));
        } else if (status === 400) {
          setSubmitError(t("auth:register.errors.invalidToken"));
        } else if (status === 409) {
          setSubmitError(t("auth:register.errors.emailExists"));
        } else {
          setSubmitError(t("auth:register.errors.failed"));
        }
      } else {
        setSubmitError(t("auth:register.errors.unexpected"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <AuthShell>
        <div className="w-full max-w-md rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth:register.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth:register.success.message")}
          </p>
          <Link
            to="/login"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("auth:register.success.backToLogin")}
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <div className="min-h-screen bg-void px-4 py-10">
      <div className="mx-auto max-w-xl">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <Logo size={28} />
          <div>
            <h1 className="text-lg font-semibold text-white/85">{t("auth:register.title")}</h1>
            <p className="text-xs text-white/35">{t("auth:register.subtitle")}</p>
          </div>
        </div>

        {/* Step indicator */}
        <div className="mb-6 flex items-center gap-2">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${step === 1 ? "bg-copper text-white" : "bg-copper/20 text-copper"}`}
          >
            {step === 2 ? "✓" : "1"}
          </div>
          <div className="h-px flex-1 bg-white/10" />
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${step === 2 ? "bg-copper text-white" : "bg-white/8 text-white/25"}`}
          >
            2
          </div>
        </div>

        {submitError && (
          <div className={`mb-5 ${errorAlertCls}`}>{submitError}</div>
        )}

        {step === 1 && (
          <RegisterStep1Form
            form={form}
            fieldErrors={fieldErrors}
            emailPreFilled={emailPreFilled}
            logoInputRef={logoInputRef}
            onFieldChange={handleChange}
            onFieldBlur={handleBlur}
            onLogoChange={handleLogoChange}
            onNext={handleNext}
          />
        )}

        {step === 2 && (
          <RegisterStep2Form
            termsAccepted={termsAccepted}
            privacyAccepted={privacyAccepted}
            fieldErrors={fieldErrors}
            submitting={submitting}
            sigCanvasRef={sigCanvasRef}
            onTermsChange={(accepted) => {
              setTermsAccepted(accepted);
              if (accepted) setFieldErrors((prev) => ({ ...prev, terms: "" }));
            }}
            onPrivacyChange={(accepted) => {
              setPrivacyAccepted(accepted);
              if (accepted) setFieldErrors((prev) => ({ ...prev, privacy: "" }));
            }}
            onSignatureBegin={() => setFieldErrors((prev) => ({ ...prev, signature: "" }))}
            onOpenContract={() => setContractOpen(true)}
            onOpenTerms={() => setTermsOpen(true)}
            onOpenPrivacy={() => setPrivacyOpen(true)}
            onBack={() => { setStep(1); setSubmitError(null); }}
            onSubmit={handleSubmit}
          />
        )}

        <p className="mt-6 text-center text-xs text-white/30">
          {t("auth:register.haveAccount")}{" "}
          <Link to="/login" className="text-copper transition hover:text-gold">
            {t("auth:register.loginLink")}
          </Link>
        </p>
      </div>

      <RegisterModals
        contractOpen={contractOpen}
        termsOpen={termsOpen}
        privacyOpen={privacyOpen}
        onCloseContract={() => setContractOpen(false)}
        onCloseTerms={() => setTermsOpen(false)}
        onClosePrivacy={() => setPrivacyOpen(false)}
        onAcceptTerms={() => {
          setTermsAccepted(true);
          setFieldErrors((prev) => ({ ...prev, terms: "" }));
          setTermsOpen(false);
        }}
        onAcceptPrivacy={() => {
          setPrivacyAccepted(true);
          setFieldErrors((prev) => ({ ...prev, privacy: "" }));
          setPrivacyOpen(false);
        }}
      />
    </div>
  );
}

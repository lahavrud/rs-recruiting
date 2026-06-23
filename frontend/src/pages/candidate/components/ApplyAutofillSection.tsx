import { useState, type ChangeEvent, type FormEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { patchMe, type CandidateMeRead } from "@/services/candidate";
import { INPUT_CLS } from "@/styles/forms";

import ResumeCard from "./ResumeCard";

// These fields exist purely to prefill the public apply form for returning
// candidates. They are NOT identity — clearing them is allowed; the
// apply-form endpoint will prompt for them inline if a live application is
// missing the data. The "live application requires phone+resume" invariant
// lives at the apply endpoint, not on the profile.
export default function ApplyAutofillSection({
  me,
  onChange,
}: {
  me: CandidateMeRead;
  onChange: (next: CandidateMeRead) => void;
}) {
  const { t } = useTranslation(['candidate', 'https']);
  const [phone, setPhone] = useState(me.phone ?? "");
  const [linkedin, setLinkedin] = useState(me.linkedin_url ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [state, setState] = useState<"idle" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setState("idle");
    setError(null);
    try {
      const updated = await patchMe({
        phone: phone.trim() ? phone : null,
        linkedin_url: linkedin.trim() ? linkedin : null,
      });
      onChange(updated);
      setState("saved");
    } catch (err) {
      setState("error");
      setError(
        axios.isAxiosError(err) && err.response?.status === 422
          ? t("candidate:profile.autofill.errors.validation")
          : t("candidate:profile.autofill.errors.generic"),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-xl border border-white/8 bg-card p-6">
      <header className="mb-5">
        <h2 className="text-base font-semibold text-white/85">
          {t("candidate:profile.autofill.title")}
        </h2>
        <p className="mt-1 text-xs text-white/45">
          {t("candidate:profile.autofill.subtitle")}
        </p>
      </header>

      {/* Mobile (default) collapses to a single ``minmax(0,1fr)`` track
          so the grid item width is clamped to the parent's width and
          ``w-full`` inputs inside can't push the row past the viewport.
          Without an explicit minmax(0,…) the implicit track has
          ``min-width: auto`` and grows with content. */}
      <div className="grid gap-6 grid-cols-[minmax(0,1fr)] sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {/* ── Left column: phone + LinkedIn ────────────────────────── */}
        <form onSubmit={handleSubmit} className="min-w-0 space-y-4">
          <Field
            label={t("candidate:profile.autofill.phone")}
            hint={t("candidate:profile.autofill.phoneHint")}
          >
            <input
              type="tel"
              value={phone}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setPhone(e.target.value)
              }
              className={INPUT_CLS}
              dir="ltr"
              placeholder="050-000-0000"
              maxLength={30}
            />
          </Field>
          <Field
            label={t("candidate:profile.autofill.linkedin")}
            hint={t("candidate:profile.autofill.linkedinHint")}
          >
            <input
              type="url"
              value={linkedin}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setLinkedin(e.target.value)
              }
              className={INPUT_CLS}
              dir="ltr"
              placeholder="https://linkedin.com/in/your-handle"
              maxLength={500}
            />
          </Field>

          <div className="flex items-center justify-between gap-3">
            <div className="text-xs">
              {state === "saved" && (
                <span className="text-copper">
                  {t("candidate:profile.autofill.saved")}
                </span>
              )}
              {state === "error" && error && (
                <span className="text-danger">{error}</span>
              )}
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting
                ? t("candidate:profile.autofill.saving")
                : t("candidate:profile.autofill.save")}
            </Button>
          </div>
        </form>

        {/* ── Right column: resume picker ──────────────────────────── */}
        <ResumeCard me={me} onChange={onChange} />
      </div>
    </section>
  );
}

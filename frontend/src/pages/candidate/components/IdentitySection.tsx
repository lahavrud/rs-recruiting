import { useState, type ChangeEvent, type FormEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { patchMe, type CandidateMeRead } from "@/services/candidate";
import { INPUT_CLS } from "@/styles/forms";

function initialsFor(name: string, email: string): string {
  const source = name?.trim() || email?.split("@", 1)[0] || "";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function IdentitySection({
  me,
  onChange,
}: {
  me: CandidateMeRead;
  onChange: (next: CandidateMeRead) => void;
}) {
  const { t } = useTranslation('candidate');
  const [fullName, setFullName] = useState(me.full_name);
  const [submitting, setSubmitting] = useState(false);
  const [state, setState] = useState<"idle" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setState("idle");
    setError(null);
    try {
      const updated = await patchMe({ full_name: fullName });
      onChange(updated);
      setState("saved");
    } catch (err) {
      setState("error");
      setError(
        axios.isAxiosError(err) && err.response?.status === 422
          ? t("candidate:profile.identity.errors.validation")
          : t("candidate:profile.identity.errors.generic"),
      );
    } finally {
      setSubmitting(false);
    }
  }

  // Two-letter initials from the current input (so it updates live as
  // the candidate edits their name) — fall back to the first letter of
  // the email local-part if the name is somehow blank.
  const initials = initialsFor(fullName, me.email);

  return (
    <section className="relative overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-br from-card-raised via-card to-card p-5 sm:p-6">
      {/* Subtle copper accent so the hero card visually leads the page
          without looking like every other card below it. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -top-12 -end-12 size-32 rounded-full bg-copper/10 blur-3xl"
      />
      <form
        onSubmit={handleSubmit}
        className="relative flex flex-col gap-4 sm:flex-row sm:items-center"
      >
        {/* Initials avatar — anchors the strip on the start edge. */}
        <div className="flex size-14 shrink-0 items-center justify-center rounded-full border border-copper/30 bg-copper/10 font-wordmark text-lg text-copper sm:size-16 sm:text-xl">
          {initials}
        </div>

        {/* Editable name on top, read-only email below. ``min-w-0`` is
            essential here — without it the ``w-full`` input below
            doesn't actually constrain to the parent flex column and
            the whole row overflows the viewport on narrow screens. */}
        <div className="min-w-0 flex-1 space-y-2">
          <Field label={t("candidate:profile.identity.fullName")}>
            <input
              type="text"
              value={fullName}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setFullName(e.target.value)
              }
              className={INPUT_CLS}
              required
              minLength={2}
              maxLength={100}
            />
          </Field>
          <p
            className="truncate text-xs text-white/45"
            title={t("candidate:profile.identity.emailLockedHint")}
          >
            <span dir="ltr">{me.email}</span>
            <span className="mx-1.5 text-white/25">·</span>
            <span className="text-white/30">
              {t("candidate:profile.identity.emailLockedHint")}
            </span>
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          <Button type="submit" disabled={submitting}>
            {submitting
              ? t("candidate:profile.identity.saving")
              : t("candidate:profile.identity.save")}
          </Button>
          <span
            aria-live="polite"
            className={`text-[11px] ${
              state === "saved"
                ? "text-copper"
                : state === "error"
                  ? "text-danger"
                  : "text-transparent"
            }`}
          >
            {state === "saved"
              ? t("candidate:profile.identity.saved")
              : state === "error" && error
                ? error
                : /* keep height stable */ "‎"}
          </span>
        </div>
      </form>
    </section>
  );
}

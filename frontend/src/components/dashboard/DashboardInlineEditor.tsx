import { useRef, useState, type ChangeEvent } from "react";

import { useTranslation } from "react-i18next";

import {
  patchMe,
  uploadResume,
  type CandidateMeRead,
} from "@/services/candidate";
import { INPUT_CLS } from "@/styles/forms";

export type MissingKey = "phone" | "linkedin" | "resume";

/**
 * Single-purpose inline editor that PATCHes /api/candidate/me (phone /
 * linkedin) or POSTs the resume upload, then bubbles the updated
 * profile back up so the parent re-evaluates which chips remain.
 */
export function InlineEditor({
  field,
  me,
  onSaved,
  onCancel,
}: {
  field: MissingKey;
  me: CandidateMeRead;
  onSaved: (next: CandidateMeRead) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation(['common', 'dashboard', 'https']);
  const [value, setValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSave() {
    setIsSubmitting(true);
    setError(null);
    try {
      const trimmed = value.trim();
      if (!trimmed) {
        setError(t("dashboard:candidate.profileCompletion.inline.required"));
        setIsSubmitting(false);
        return;
      }
      const patch =
        field === "phone" ? { phone: trimmed } : { linkedin_url: trimmed };
      const next = await patchMe(patch);
      onSaved(next);
    } catch {
      setError(t("dashboard:candidate.profileCompletion.inline.error"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResumePick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const next = await uploadResume(file);
      onSaved(next);
    } catch {
      setError(t("dashboard:candidate.profileCompletion.inline.resumeError"));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (field === "resume") {
    // Resume needs a file picker — no text input. Keep the row uniform
    // by rendering a button that delegates to a hidden file input.
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] text-white/55">
          {t("dashboard:candidate.profileCompletion.inline.resumeHint")}
        </span>
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isSubmitting}
          className="rounded-sm bg-copper px-3 py-1 text-xs font-medium text-white transition hover:bg-gold disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting
            ? t("common:submitting")
            : t("dashboard:candidate.profileCompletion.inline.resumePick")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-[11px] text-white/45 transition hover:text-white/70"
        >
          {t("common:cancel")}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          className="sr-only"
          onChange={handleResumePick}
        />
        {error && (
          <p className="basis-full text-[11px] text-danger">{error}</p>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type={field === "phone" ? "tel" : "url"}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void handleSave();
          }
        }}
        autoFocus
        dir="ltr"
        placeholder={
          field === "phone"
            ? "050-000-0000"
            : "https://linkedin.com/in/your-handle"
        }
        className={`${INPUT_CLS} max-w-xs py-1.5 text-xs`}
        maxLength={field === "phone" ? 30 : 500}
      />
      <button
        type="button"
        onClick={handleSave}
        disabled={isSubmitting || !value.trim()}
        className="rounded-sm bg-copper px-3 py-1.5 text-xs font-medium text-white transition hover:bg-gold disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? t("common:submitting") : t("common:save")}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-[11px] text-white/45 transition hover:text-white/70"
      >
        {t("common:cancel")}
      </button>
      {error && <p className="basis-full text-[11px] text-danger">{error}</p>}
      {/* When the user is touching the linkedin field we suppress the
          placeholder and let `me` hint at their existing value if they
          previously typed one in. */}
      {field === "linkedin" && me.linkedin_url === null && !value && (
        <p className="basis-full text-[11px] text-white/40">
          {t("dashboard:candidate.profileCompletion.inline.linkedinHint")}
        </p>
      )}
    </div>
  );
}

import { useState, type ChangeEvent } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";

import {
  deleteResume,
  patchMe,
  uploadResume,
  type CandidateMeRead,
} from "@/services/candidate";

/** Split a filename into editable basename + locked extension (no dot). */
function splitFilename(name: string | null): { base: string; ext: string } {
  if (!name) return { base: "", ext: "" };
  const idx = name.lastIndexOf(".");
  if (idx <= 0 || idx === name.length - 1) return { base: name, ext: "" };
  return { base: name.slice(0, idx), ext: name.slice(idx + 1) };
}

/**
 * Resume slot inside the apply-autofill card. Visually distinct from
 * the text fields on the left: a labelled, full-height tile with the
 * current resume's filename badge at the top and a drop/upload zone
 * underneath. When no resume is set, the tile becomes a single
 * dashed-border upload affordance.
 */
export default function ResumeCard({
  me,
  onChange,
}: {
  me: CandidateMeRead;
  onChange: (next: CandidateMeRead) => void;
}) {
  const { t } = useTranslation('candidate');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Rename UX: candidate clicks the displayed filename to swap into
  // edit mode. Only the basename is editable — the extension is locked
  // to the bytes on disk (server enforces; UI rejects too).
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await uploadResume(file);
      onChange(updated);
    } catch (err) {
      setError(
        axios.isAxiosError(err) && err.response?.status === 422
          ? t("candidate:profile.resume.errors.invalidFile")
          : t("candidate:profile.resume.errors.generic"),
      );
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleDelete() {
    if (!confirm(t("candidate:profile.resume.confirmDelete"))) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await deleteResume();
      onChange(updated);
    } catch {
      setError(t("candidate:profile.resume.errors.generic"));
    } finally {
      setBusy(false);
    }
  }

  // Prefer the candidate-supplied label (`resume_filename`); fall back
  // to the basename of the storage key for legacy rows that pre-date
  // the column. The extension is always taken from whichever source we
  // end up displaying — it's the canonical lock for the rename UI.
  const displayName = me.resume_filename
    ? me.resume_filename
    : me.resume_path
      ? me.resume_path.split("/").pop() ?? me.resume_path
      : null;
  const { base: displayBase, ext: displayExt } = splitFilename(displayName);

  function startRename() {
    if (!displayName) return;
    setRenameValue(displayBase);
    setRenaming(true);
    setError(null);
  }
  function cancelRename() {
    setRenaming(false);
    setRenameValue("");
    setError(null);
  }
  async function commitRename() {
    if (!displayName) return;
    const trimmedBase = renameValue.trim();
    // Blank or unchanged → silent cancel. No "save empty" UX path:
    // the candidate intent was clearly to back out, not to wipe the
    // label. They can use the Remove button to clear the resume.
    const nextName = displayExt ? `${trimmedBase}.${displayExt}` : trimmedBase;
    if (!trimmedBase || nextName === displayName) {
      cancelRename();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await patchMe({ resume_filename: nextName });
      onChange(updated);
      setRenaming(false);
      setRenameValue("");
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 422) {
        setError(t("candidate:profile.resume.renameErrors.invalid"));
      } else {
        setError(t("candidate:profile.resume.errors.generic"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col">
      <label className="block text-xs text-white/55">
        {t("candidate:profile.resume.title")}
      </label>
      <div className="mt-1.5 flex-1">
        {displayName ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-white/10 bg-card-raised px-4 py-5 text-center">
            {/* Icon on top — anchors the card without competing with
                the name underneath. */}
            <span className="flex size-10 items-center justify-center rounded-md bg-copper/15 text-copper">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                className="size-5"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6"
                />
              </svg>
            </span>

            {/* Filename — click to rename. Edit mode swaps in an input
                that auto-saves on blur (or Enter); Escape cancels. */}
            <div className="w-full min-w-0">
              {renaming ? (
                <div
                  className="flex items-center justify-center gap-1"
                  dir="ltr"
                >
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => void commitRename()}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        (e.target as HTMLInputElement).blur();
                      } else if (e.key === "Escape") {
                        cancelRename();
                      }
                    }}
                    autoFocus
                    maxLength={Math.max(1, 100 - (displayExt.length + 1))}
                    className="min-w-0 max-w-full rounded-sm border border-copper/40 bg-well px-2 py-1 text-center text-sm font-medium text-white/90 focus:outline-none focus:ring-1 focus:ring-copper/50"
                    aria-label={t(
                      "candidate:profile.resume.renameInputLabel",
                    )}
                  />
                  {displayExt && (
                    <span className="shrink-0 text-sm text-white/45">
                      .{displayExt}
                    </span>
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={startRename}
                  className="group/rename block w-full min-w-0"
                  title={t("candidate:profile.resume.renameTooltip")}
                >
                  <span
                    className="block truncate text-sm font-medium text-white/85 transition group-hover/rename:text-copper"
                    dir="ltr"
                  >
                    {displayName}
                  </span>
                </button>
              )}
              <p className="mt-1 text-[11px] text-white/40">
                {renaming
                  ? t("candidate:profile.resume.renameHint")
                  : t("candidate:profile.resume.attachedHint")}
              </p>
            </div>

            {/* Replace + Remove always render — even while renaming,
                clicking them blurs the input which commits the rename
                first. Simpler than juggling two action modes. */}
            <div className="flex items-center justify-center gap-2">
              <label className="cursor-pointer rounded-sm border border-white/20 px-3 py-1.5 text-xs text-white/70 transition hover:border-white/40 hover:text-white">
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  className="hidden"
                  onChange={handleUpload}
                  disabled={busy}
                />
                {t("candidate:profile.resume.replace")}
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={handleDelete}
                className="rounded-sm border border-danger/40 px-3 py-1.5 text-xs text-danger/80 transition hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("candidate:profile.resume.remove")}
              </button>
            </div>
          </div>
        ) : (
          <label className="group flex h-full min-h-[140px] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-white/15 bg-card-raised/40 p-4 text-center transition hover:border-copper/50 hover:bg-card-raised">
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              className="hidden"
              onChange={handleUpload}
              disabled={busy}
            />
            <span className="flex size-10 items-center justify-center rounded-full border border-copper/30 bg-copper/10 text-copper transition group-hover:border-copper/60 group-hover:bg-copper/15">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                className="size-4"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 16V4m0 0-4 4m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                />
              </svg>
            </span>
            <span className="text-sm font-medium text-white/75">
              {t("candidate:profile.resume.upload")}
            </span>
            <span className="text-[11px] text-white/40">
              {t("candidate:profile.resume.uploadHint")}
            </span>
          </label>
        )}
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}

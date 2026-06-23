import { type ChangeEvent, type DragEvent, useRef, useState } from "react";

import { useTranslation } from "react-i18next";

import { RESUME_MAX_FILE_SIZE_MB } from "@/utils/resume";

export default function ResumeStep({
  file,
  error,
  savedResumeFilename,
  onFile,
  onPick,
  onClear,
  onClearSaved,
}: {
  file: File | null;
  error: string | null;
  savedResumeFilename: string | null;
  onFile: (f: File | null) => void;
  onPick: (e: ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
  onClearSaved: () => void;
}) {
  const { t } = useTranslation('publicJobs');
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function onDragOver(e: DragEvent<HTMLButtonElement>) {
    e.preventDefault();
    if (!isDragging) setIsDragging(true);
  }
  function onDragLeave() {
    setIsDragging(false);
  }
  function onDrop(e: DragEvent<HTMLButtonElement>) {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0] ?? null;
    onFile(dropped);
  }

  // Logged-in candidate w/ a profile resume on file and no new pick yet —
  // show the "use saved resume" card so submitting w/o an upload reuses
  // it server-side (no extra storage cost, no re-upload).
  const isShowingSavedResume = !file && savedResumeFilename;

  return (
    <div>
      {isShowingSavedResume ? (
        <div className="flex items-center gap-3 rounded-xl border border-copper/30 bg-card-raised p-4">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-copper/15 text-copper">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
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
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white/85">
              {savedResumeFilename}
            </p>
            <p className="mt-0.5 text-xs text-white/40">
              {t("publicJobs:application.resumeSavedHint")}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onClearSaved();
              inputRef.current?.click();
            }}
            className="shrink-0 rounded-sm border border-white/15 px-3 py-1.5 text-xs text-white/65 transition hover:border-copper/50 hover:text-copper"
          >
            {t("publicJobs:application.resumeReplace")}
          </button>
        </div>
      ) : file ? (
        <div className="flex items-center gap-3 rounded-xl border border-copper/30 bg-card-raised p-4">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-copper/15 text-copper">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
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
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white/85">
              {file.name}
            </p>
            <p className="mt-0.5 text-xs text-white/40">
              {t("publicJobs:application.fileSizeBytes", {
                kb: Math.round(file.size / 1024).toLocaleString("he-IL"),
              })}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onClear();
              inputRef.current?.click();
            }}
            className="shrink-0 rounded-sm border border-white/15 px-3 py-1.5 text-xs text-white/65 transition hover:border-copper/50 hover:text-copper"
          >
            {t("publicJobs:application.resumeReplace")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          aria-label={t("publicJobs:application.resumeUpload")}
          className={[
            "flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors duration-200",
            isDragging
              ? "border-copper bg-copper/10"
              : "border-white/15 bg-card hover:border-copper/40 hover:bg-card-raised",
          ].join(" ")}
        >
          <span
            className={`flex size-12 items-center justify-center rounded-full border transition-colors ${
              isDragging
                ? "border-copper bg-copper/20 text-copper"
                : "border-copper/30 bg-copper/10 text-copper"
            }`}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="size-5"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 16V4m0 0-4 4m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
              />
            </svg>
          </span>
          <span className="text-sm font-medium text-white/80">
            {t("publicJobs:application.resumeDropPrompt")}
          </span>
          <span className="text-xs text-white/45">
            {t("publicJobs:application.resumeDropAlt")}
          </span>
        </button>
      )}

      <input
        ref={inputRef}
        id="resume"
        name="resume"
        type="file"
        accept=".pdf,.doc,.docx"
        onChange={onPick}
        className="sr-only"
      />

      {error && <p className="mt-3 text-xs text-danger">{error}</p>}
      <p className="mt-3 text-xs text-white/30">
        {t("publicJobs:application.fileHint", { maxSize: RESUME_MAX_FILE_SIZE_MB })}
      </p>
    </div>
  );
}

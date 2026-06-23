import { useEffect, useState } from "react";

import axios from "axios";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { fetchResumeBlob } from "@/services/adminCandidates";
import {
  buildResumeDownloadName,
  downloadOrShareBlob,
  isInlinePreviewable,
  isIOS,
} from "@/utils/resume";

type LoadState = "loading" | "ready" | "notFound" | "error";

/**
 * Fullscreen on-demand resume viewer. The single source of truth for how the
 * app shows a candidate's resume.
 *
 * Flow:
 *   1. Fetch the blob on mount (admin endpoint streams the file)
 *   2. PDFs → render inline via `<iframe>` (browsers handle PDF natively).
 *      iOS WebKit is the exception — Mobile Safari and all iOS browsers
 *      (which all use WebKit) refuse to render PDFs from blob: URLs in
 *      iframes, so iOS users go through the same fallback path as DOCs.
 *   3. DOC/DOCX/other AND any file on iOS → friendly "no preview" panel
 *      with a download button. The download path on iOS uses Web Share,
 *      which surfaces Quick Look (≈ a preview) + Save to Files + Open in…
 *   4. Header exposes download + open-in-new-tab whenever inline preview
 *      is active so users can save / pop out without leaving the viewer
 *   5. 404 → distinct "file not available" state (no download/open offered)
 *
 * Not built on the shared `<Dialog>` because Dialog caps at max-w-2xl and is
 * centered — a resume needs the entire viewport for readability.
 */
export function ResumeViewer({
  candidateName,
  resumePath,
  onClose,
}: {
  candidateName: string;
  resumePath: string;
  onClose: () => void;
}) {
  const { t } = useTranslation(['common', 'http', 'resume']);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  // `resume_path` from the DB is `resumes/<basename>`. The download endpoint
  // wants only the basename — split it once here.
  const fileKey = resumePath.split("/").pop() ?? resumePath;
  const mimeType = blob?.type || "application/octet-stream";
  // Inline preview requires both a previewable MIME type AND a browser that
  // can actually render it. iOS WebKit can't render PDFs in blob: iframes —
  // treat iOS as never-previewable so users get the Web Share fallback.
  const previewable =
    blob != null && isInlinePreviewable(mimeType, fileKey) && !isIOS();
  const downloadName = blob
    ? buildResumeDownloadName(candidateName, fileKey, mimeType)
    : "";

  // Lock body scroll + Escape to close
  useEffect(() => {
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onEsc);
    return () => {
      document.body.style.overflow = original;
      window.removeEventListener("keydown", onEsc);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch blob → hold both blob (for download/share) and an object URL (for
  // iframe / open-in-new-tab). Revoke the URL on unmount.
  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    fetchResumeBlob(fileKey)
      .then((b) => {
        if (cancelled) return;
        url = URL.createObjectURL(b);
        setBlob(b);
        setObjectUrl(url);
        setLoadState("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const status = axios.isAxiosError(err) ? err.response?.status : undefined;
        setLoadState(status === 404 ? "notFound" : "error");
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [fileKey]);

  async function handleDownload() {
    if (!blob) return;
    await downloadOrShareBlob(blob, downloadName);
  }

  // Header actions only when the file is loaded AND previewable. For the
  // unsupported case, the body renders the download button itself.
  const headerActions = loadState === "ready" && previewable && blob && objectUrl && (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={handleDownload}
        className="inline-flex items-center gap-1.5 rounded-sm border border-white/10 px-3 py-1.5 text-xs text-white/65 hover:border-copper/40 hover:text-white"
      >
        {t("resume:download")}
      </button>
      <a
        href={objectUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 rounded-sm border border-white/10 px-3 py-1.5 text-xs text-white/65 hover:border-copper/40 hover:text-white"
      >
        {t("resume:openNewTab")} ↗
      </a>
    </div>
  );

  // Portal to document.body so `fixed inset-0` is anchored to the viewport,
  // not whichever ancestor happens to be transformed (Radix Dialog content,
  // AppShell's page-enter animation, etc. — all create containing blocks).
  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex flex-col bg-black/80 backdrop-blur pointer-events-auto"
      dir="rtl"
      onClick={onClose}
    >
      <div
        className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/8 bg-void/80 px-4 py-3 sm:px-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="min-w-0">
          <p className="text-[11px] text-white/40">{t("resume:header")}</p>
          <p className="truncate text-sm text-white/85">{candidateName}</p>
        </div>
        <div className="flex items-center gap-2">
          {headerActions}
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-2 rounded-sm border border-white/10 px-3 py-1.5 text-xs text-white/60 hover:border-white/30 hover:text-white"
            aria-label={t("common:close")}
          >
            <IconClose />
            <span>{t("common:close")}</span>
          </button>
        </div>
      </div>

      <div
        className="flex-1 overflow-hidden bg-white/5"
        onClick={(e) => e.stopPropagation()}
      >
        {loadState === "loading" && (
          <div className="flex h-full items-center justify-center text-sm text-white/50">
            {t("common:loading")}
          </div>
        )}
        {loadState === "notFound" && (
          <div className="flex h-full items-center justify-center px-6 text-center">
            <div className="max-w-md text-white/75">
              <h2 className="text-lg font-light text-white/90">
                {t("resume:notFound")}
              </h2>
              <p className="mt-2 text-sm text-white/55">{t("resume:notFoundDetail")}</p>
            </div>
          </div>
        )}
        {loadState === "error" && (
          <div className="flex h-full items-center justify-center text-sm text-white/60">
            {t("resume:error")}
          </div>
        )}
        {loadState === "ready" && objectUrl && (
          previewable ? (
            <iframe
              src={objectUrl}
              title={`${t("resume:header")} — ${candidateName}`}
              className="h-full w-full border-0"
            />
          ) : (
            <UnsupportedPreview onDownload={handleDownload} />
          )
        )}
      </div>
    </div>,
    document.body,
  );
}

/** Body shown when the file can't render inline (DOC/DOCX). */
function UnsupportedPreview({ onDownload }: { onDownload: () => void }) {
  const { t } = useTranslation(['common', 'http', 'resume']);
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="max-w-md text-center text-white/75">
        <div className="mx-auto inline-flex size-12 items-center justify-center rounded-full border border-white/15 bg-white/5 text-white/60">
          <IconDocument className="size-5" />
        </div>
        <h2 className="mt-4 text-lg font-light text-white/90">
          {t("resume:unsupportedTitle")}
        </h2>
        <p className="mt-2 text-sm text-white/55">{t("resume:unsupportedSubtitle")}</p>
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={onDownload}
            className="inline-flex items-center gap-2 rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("resume:download")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Icons (kept local to this file so it has no cross-feature imports) ── */

function IconClose({ className = "size-3.5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M4 4 L12 12 M12 4 L4 12" />
    </svg>
  );
}

function IconDocument({ className = "size-4" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M4 2 H10 L13 5 V14 H4 Z M10 2 V5 H13 M6 9 H11 M6 11.5 H11" />
    </svg>
  );
}

/**
 * Inline button that opens the viewer for a resume. Drop-in replacement for
 * the old `ResumeLink` (which downloaded / opened-in-tab directly).
 */
export default function ResumeButton({
  resumePath,
  candidateName,
  label,
  className,
  onOpenChange,
}: {
  resumePath: string;
  candidateName: string;
  /** Override the default trigger label (defaults to `t('resume.triggerLabel')`). */
  label?: string;
  className?: string;
  /** Called whenever the viewer opens or closes — lets a parent Dialog lock
   *  its preventOutsideClose while the viewer is visible. */
  onOpenChange?: (open: boolean) => void;
}) {
  const { t } = useTranslation(['common', 'http', 'resume']);
  const [isOpen, setIsOpen] = useState(false);
  const text = label ?? t("resume:triggerLabel");

  function handleSetOpen(v: boolean) {
    setIsOpen(v);
    onOpenChange?.(v);
  }

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          handleSetOpen(true);
        }}
        className={
          className ??
          "text-copper hover:text-gold transition-colors"
        }
      >
        {text} ↗
      </button>
      {isOpen && (
        <ResumeViewer
          candidateName={candidateName}
          resumePath={resumePath}
          onClose={() => handleSetOpen(false)}
        />
      )}
    </>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";

import axios from "axios";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import Button from "@/components/ui/Button";
import Logo from "@/components/ui/Logo";
import { logout as logoutService } from "@/services/auth";
import { checkDeletionToken, confirmAccountDeletion } from "@/services/candidate";

import AuthShell from "../components/AuthShell";

type State = "checking" | "confirming" | "deleting" | "success" | "error";

/** Why the flow failed. Drives which copy and which exit the error card offers. */
type ErrorKind = "invalid" | "tooMany" | "failed";

/** A rate-limited or offline request leaves the link perfectly usable, so those
 *  must not be reported as an invalid link — only a 400 means the token is dead. */
function errorKindFor(error: unknown): ErrorKind {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    if (status === 400) return "invalid";
    if (status === 429) return "tooMany";
  }
  return "failed";
}

const ERROR_COPY: Record<ErrorKind, { title: string; message: string }> = {
  invalid: {
    title: "candidate:deleteConfirm.error.title",
    message: "candidate:deleteConfirm.error.message",
  },
  tooMany: {
    title: "candidate:deleteConfirm.error.tooManyTitle",
    message: "candidate:deleteConfirm.error.tooMany",
  },
  failed: {
    title: "candidate:deleteConfirm.error.failedTitle",
    message: "candidate:deleteConfirm.error.failed",
  },
};

export default function DeleteAccountConfirmPage() {
  const { t } = useTranslation("candidate");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>(() => (token ? "checking" : "error"));
  const [errorKind, setErrorKind] = useState<ErrorKind>("invalid");
  const headingRef = useRef<HTMLHeadingElement>(null);

  const runCheck = useCallback(() => {
    if (!token) return;
    checkDeletionToken(token)
      .then(() => setState("confirming"))
      .catch((err) => {
        setErrorKind(errorKindFor(err));
        setState("error");
      });
  }, [token]);

  useEffect(() => {
    runCheck();
  }, [runCheck]);

  // Pull focus to the outcome so the transition isn't silent for screen readers.
  useEffect(() => {
    if (state === "success" || state === "error") headingRef.current?.focus();
  }, [state]);

  function handleRetry() {
    setState("checking");
    runCheck();
  }

  async function handleConfirm() {
    if (!token) return;
    setState("deleting");
    try {
      await confirmAccountDeletion(token);
      // The User row is gone server-side. Drop the local session too, or the app
      // keeps rendering as authenticated until the access token expires.
      logoutService();
      setState("success");
    } catch (err) {
      setErrorKind(errorKindFor(err));
      setState("error");
    }
  }

  if (state === "checking" || state === "deleting") {
    return (
      <AuthShell>
        <p className="text-sm text-white/30" role="status" aria-live="polite">
          {t(
            state === "checking"
              ? "candidate:deleteConfirm.loading"
              : "candidate:deleteConfirm.confirming",
          )}
        </p>
      </AuthShell>
    );
  }

  if (state === "success") {
    return (
      <AuthShell>
        <div
          className="w-full max-w-md rounded-xl border border-success/20 bg-success/8 p-10 text-center"
          role="status"
          aria-live="polite"
        >
          <div className="flex justify-center">
            <Logo size={32} />
          </div>
          <div
            className="mx-auto mt-6 flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success"
            aria-hidden="true"
          >
            ✓
          </div>
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="mt-5 text-lg font-semibold text-white/90 outline-none"
          >
            {t("candidate:deleteConfirm.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("candidate:deleteConfirm.success.message")}
          </p>
          <Button
            variant="ghost"
            size="lg"
            className="mt-7"
            // Full document load: AuthContext resolves from localStorage on mount,
            // so a client-side navigate would keep the deleted user in memory.
            onClick={() => window.location.replace("/")}
          >
            {t("candidate:deleteConfirm.success.backHome")}
          </Button>
        </div>
      </AuthShell>
    );
  }

  if (state === "error") {
    const copy = ERROR_COPY[errorKind];
    return (
      <AuthShell>
        <div
          className="w-full max-w-md rounded-xl border border-danger/20 bg-danger/8 p-10 text-center"
          role="alert"
        >
          <div
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-lg text-danger"
            aria-hidden="true"
          >
            ✕
          </div>
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="mt-5 text-lg font-semibold text-white/90 outline-none"
          >
            {t(copy.title)}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">{t(copy.message)}</p>
          {errorKind === "invalid" ? (
            <Button
              variant="ghost"
              size="lg"
              className="mt-7"
              // Not /candidate/profile: this page is public and reached from an
              // email, so anonymous requesters would just bounce off the guard.
              onClick={() => navigate("/login")}
            >
              {t("candidate:deleteConfirm.error.backToLogin")}
            </Button>
          ) : (
            <Button variant="ghost" size="lg" className="mt-7" onClick={handleRetry}>
              {t("candidate:deleteConfirm.error.retry")}
            </Button>
          )}
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div className="w-full max-w-md rounded-xl border border-danger/25 bg-danger/5 p-10 text-center">
        <div className="flex justify-center">
          <Logo size={32} />
        </div>
        <div className="mx-auto mt-6 flex h-12 w-12 items-center justify-center rounded-full border border-danger/30 bg-danger/10">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="size-6 text-danger/80"
            aria-hidden="true"
          >
            <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7h6m-7 0V5a2 2 0 012-2h2a2 2 0 012 2v2" />
          </svg>
        </div>
        <h2 className="mt-5 text-lg font-semibold text-white/90">
          {t("candidate:deleteConfirm.title")}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-white/50">
          {t("candidate:deleteConfirm.message")}
        </p>
        <Button variant="danger" size="lg" className="mt-7 w-full" onClick={handleConfirm}>
          {t("candidate:deleteConfirm.confirm")}
        </Button>
      </div>
    </AuthShell>
  );
}

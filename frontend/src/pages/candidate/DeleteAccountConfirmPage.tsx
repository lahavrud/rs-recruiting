import { useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import Button from "@/components/ui/Button";
import Logo from "@/components/ui/Logo";
import { confirmAccountDeletion } from "@/services/candidate";

import AuthShell from "../components/AuthShell";

type State = "loading" | "confirming" | "success" | "error";

export default function DeleteAccountConfirmPage() {
  const { t } = useTranslation("candidate");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>(() => (token ? "confirming" : "error"));

  async function handleConfirm() {
    if (!token) return;
    setState("loading");
    try {
      await confirmAccountDeletion(token);
      setState("success");
    } catch {
      setState("error");
    }
  }

  if (state === "loading") {
    return (
      <AuthShell>
        <p className="text-sm text-white/30">{t("candidate:deleteConfirm.confirming")}</p>
      </AuthShell>
    );
  }

  if (state === "success") {
    return (
      <AuthShell>
        <div className="w-full max-w-md rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="flex justify-center">
            <Logo size={32} />
          </div>
          <div className="mx-auto mt-6 flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("candidate:deleteConfirm.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("candidate:deleteConfirm.success.message")}
          </p>
        </div>
      </AuthShell>
    );
  }

  if (state === "error") {
    return (
      <AuthShell>
        <div className="w-full max-w-md rounded-xl border border-danger/20 bg-danger/8 p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-lg text-danger">
            ✕
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("candidate:deleteConfirm.error.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("candidate:deleteConfirm.error.message")}
          </p>
          <Button
            variant="ghost"
            size="lg"
            className="mt-7"
            onClick={() => navigate("/candidate/profile")}
          >
            {t("candidate:deleteConfirm.error.backToProfile")}
          </Button>
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
        <Button
          variant="danger"
          size="lg"
          className="mt-7 w-full"
          onClick={handleConfirm}
        >
          {t("candidate:deleteConfirm.confirm")}
        </Button>
      </div>
    </AuthShell>
  );
}

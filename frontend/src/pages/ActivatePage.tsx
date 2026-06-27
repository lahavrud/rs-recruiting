import { useEffect, useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import Button from "@/components/ui/Button";
import Logo from "@/components/ui/Logo";
import { activateAccount } from "@/services/auth";

import AuthShell from "./components/AuthShell";

type State = "loading" | "success" | "error";

export default function ActivatePage() {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>(() => (token ? "loading" : "error"));

  useEffect(() => {
    if (!token) return;
    activateAccount(token)
      .then(() => setState("success"))
      .catch(() => setState("error"));
  }, [token]);

  if (state === "loading") {
    return (
      <AuthShell className="">
        <p className="text-sm text-white/30">{t("auth:activate.loading")}</p>
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
            {t("auth:activate.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth:activate.success.message")}
          </p>
          <Button
            variant="primary"
            size="lg"
            className="mt-7"
            onClick={() => navigate("/login")}
          >
            {t("auth:activate.success.loginButton")}
          </Button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div className="w-full max-w-md rounded-xl border border-danger/20 bg-danger/8 p-10 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-lg text-danger">
          ✕
        </div>
        <h2 className="mt-5 text-lg font-semibold text-white/90">
          {t("auth:activate.error.title")}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-white/50">
          {t("auth:activate.error.message")}
        </p>
        <Button
          variant="ghost"
          size="lg"
          className="mt-7"
          onClick={() => navigate("/login")}
        >
          {t("auth:activate.error.backToLogin")}
        </Button>
      </div>
    </AuthShell>
  );
}

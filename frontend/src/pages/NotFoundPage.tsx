import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import Button from "@/components/ui/Button";
import SeoHead from "@/components/ui/SeoHead";

export default function NotFoundPage() {
  const { t } = useTranslation('ui');
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-page">
      <SeoHead title={t("ui:notFound.title")} description="" noIndex />
      <h1 className="text-6xl font-bold text-white/20">{t("ui:notFound.title")}</h1>
      <p className="mt-4 text-lg text-white/45">{t("ui:notFound.message")}</p>
      <Button
        variant="primary"
        size="lg"
        className="mt-6"
        onClick={() => navigate("/dashboard")}
      >
        {t("ui:notFound.goToDashboard")}
      </Button>
    </div>
  );
}

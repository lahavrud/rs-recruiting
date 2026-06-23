import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import SeoHead from "@/components/ui/SeoHead";

export default function NotFoundPage() {
  const { t } = useTranslation('ui');

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-page">
      <SeoHead title={t("ui:notFound.title")} description="" noIndex />
      <h1 className="text-6xl font-bold text-white/20">{t("ui:notFound.title")}</h1>
      <p className="mt-4 text-lg text-white/45">{t("ui:notFound.message")}</p>
      <Link
        to="/dashboard"
        className="mt-6 rounded-sm bg-copper px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gold"
      >
        {t("ui:notFound.goToDashboard")}
      </Link>
    </div>
  );
}

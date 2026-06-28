import { useTranslation } from "react-i18next";

import PageHeader from "@/components/ui/PageHeader";
import SessionsSection from "@/components/ui/SessionsSection";

export default function AdminProfilePage() {
  const { t } = useTranslation("admin");

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        eyebrow={t("admin:profile.eyebrow")}
        subtitle={t("admin:profile.subtitle")}
      />
      <div className="mt-6">
        <SessionsSection />
      </div>
    </div>
  );
}

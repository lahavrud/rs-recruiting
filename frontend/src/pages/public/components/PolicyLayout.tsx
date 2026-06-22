import { useTranslation } from "react-i18next";

import LegalProse from "@/components/ui/LegalProse";
import PageHeader from "@/components/ui/PageHeader";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";

interface PolicyLayoutProps {
  titleKey: string;
  bodyKey: string;
  canonicalPath: string;
  eyebrowKey: string;
}

export default function PolicyLayout({
  titleKey,
  bodyKey,
  canonicalPath,
  eyebrowKey,
}: PolicyLayoutProps) {
  const { t } = useTranslation(["legal", "auth"]);
  return (
    <>
      <SeoHead
        title={t(titleKey)}
        description={t(titleKey)}
        canonical={`${SITE_URL}${canonicalPath}`}
      />
      <div className="flex-1 bg-void">
        {/* Narrow reading column — ~65ch measure keeps legal text legible */}
        <div className="mx-auto max-w-2xl px-6 py-16 sm:py-24">
          <PageHeader eyebrow={t(eyebrowKey)} />
          <h1 className="text-4xl font-light tracking-tight text-white/90 sm:text-5xl">
            {t(titleKey)}
          </h1>
          <div className="mt-10 space-y-5 border-t border-white/8 pt-10">
            <LegalProse bodyKey={bodyKey} />
          </div>
        </div>
      </div>
    </>
  );
}

import { useEffect, useState } from "react";

import Lenis from "lenis";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import "lenis/dist/lenis.css";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import { useAuth } from "@/hooks/useAuth";
import { useFetch } from "@/hooks/useFetch";
import { getPublicJobs } from "@/services/jobs";

import LandingClosingCta from "./components/LandingClosingCta";
import LandingFeaturedJobs from "./components/LandingFeaturedJobs";
import LandingHero from "./components/LandingHero";
import LandingSectors from "./components/LandingSectors";

// Combined Organization + WebSite schema via @graph. WebSite gives Google a
// canonical brand entity for the domain (helps consolidate the homepage and
// /jobs into a single SERP result with sitelinks instead of two separate
// entries). EmploymentAgency is a more specific Organization subtype that
// matches the niche.
const SITE_SCHEMA = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": ["Organization", "EmploymentAgency"],
      "@id": `${SITE_URL}/#organization`,
      name: "RS Recruiting",
      url: SITE_URL,
      logo: `${SITE_URL}/logo.svg`,
      description:
        "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול מבנים ונכסים בישראל",
      areaServed: "IL",
      knowsAbout: ["ניהול מבנים", "תפעול מבנים", "ניהול נכסים", "גיוס עובדים", "השמה"],
      contactPoint: {
        "@type": "ContactPoint",
        email: "support@rs-recruiting.com",
        contactType: "כוח אדם וגיוס",
        areaServed: "IL",
        availableLanguage: "Hebrew",
      },
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: "RS Recruiting",
      inLanguage: "he-IL",
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
  ],
};

export default function LandingPage() {
  const { t } = useTranslation("landing");
  useAuth(); // keeps auth context initialised for child components
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");

  // Inertia scrolling, scoped to the landing route only — the rest of the
  // app keeps native scroll. Skipped entirely under prefers-reduced-motion.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    const lenis = new Lenis({ autoRaf: true });
    return () => lenis.destroy();
  }, []);

  const { data: jobsPage, loading: jobsLoading } = useFetch(getPublicJobs, []);
  const jobs = jobsPage?.items ?? [];

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    navigate(
      `/jobs${searchQuery.trim() ? `?q=${encodeURIComponent(searchQuery.trim())}` : ""}`,
    );
  }

  // overflow-x-clip: the hero's skewed plane and pre-reveal translated
  // elements must not widen the document.
  return (
    <div className="font-display relative overflow-x-clip bg-void">
      {/* Container guides: vertical hairlines at the content column's
          edges, running the full page over every section. Hidden below sm
          where the column spans the viewport. z-10 keeps them above section
          backgrounds. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-10 mx-auto hidden max-w-7xl border-x border-white/6 sm:block"
      />
      <SeoHead
        title={t("landing:seo.title")}
        description={t("landing:seo.description")}
        canonical={SITE_URL}
        ogImage={`${SITE_URL}/og/home.svg`}
        structuredData={SITE_SCHEMA}
      />

      <LandingHero
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchSubmit={handleSearch}
      />

      <LandingSectors />

      <LandingFeaturedJobs jobs={jobs} loading={jobsLoading} />

      <LandingClosingCta />
    </div>
  );
}

import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import Eyebrow from "@/components/ui/Eyebrow";
import FadeInImage from "@/components/ui/FadeInImage";
import SeoHead, { SITE_URL, SITE_NAME } from "@/components/ui/SeoHead";
import { getArticle } from "@/content/articles";
import { useFetch } from "@/hooks/useFetch";
import { getPublicJobs } from "@/services/jobs";
import { formatDateLong as formatDate } from "@/utils/formatDate";

const RELATED_JOBS_LIMIT = 6;

function formatSalary(min: number | null, max: number | null): string | null {
  if (!min && !max) return null;
  const fmt = (n: number) => n.toLocaleString("he-IL");
  if (min && max) return `${fmt(min)}–${fmt(max)} ₪`;
  if (min) return `מ-${fmt(min)} ₪`;
  return `עד ${fmt(max!)} ₪`;
}

function RelatedJobs() {
  const { t } = useTranslation(["https", "ui"]);
  // Silent on failure — the section just won't render if the API is down.
  const { data: jobs, loading: isLoading } = useFetch(
    () => getPublicJobs().then((page) => page.items.slice(0, RELATED_JOBS_LIMIT)),
    [],
  );

  if (isLoading || !jobs || jobs.length === 0) return null;

  return (
    <section className="mt-16 border-t border-white/8 pt-10">
      <Eyebrow>משרות פתוחות</Eyebrow>
      <div className="mt-3 h-px w-8 bg-copper/40" />
      <h2 className="mt-4 text-xl font-semibold text-white/90 sm:text-2xl">
        משרות פתוחות בתחום
      </h2>
      <p className="mt-2 text-sm text-white/45">
        משרות אקטואליות שאנחנו מגייסים אליהן עכשיו בתחום ניהול ותפעול מבנים ונכסים.
      </p>

      <ul className="mt-6 grid gap-3 sm:grid-cols-2">
        {jobs.map((j) => {
          const salary = formatSalary(j.salary_min, j.salary_max);
          return (
            <li key={j.id}>
              <Link
                to={`/jobs/${j.id}`}
                className="block h-full rounded-xl border border-white/8 bg-card p-5 transition hover:border-copper/40 hover:bg-card-raised"
              >
                <h3 className="text-sm font-semibold text-white/90">{j.title}</h3>
                <p className="mt-1.5 text-xs text-white/45">{j.location}</p>
                {salary && <p className="mt-2 text-xs text-copper/80">{salary}</p>}
              </Link>
            </li>
          );
        })}
      </ul>

      <Link
        to="/jobs"
        className="mt-6 inline-block text-sm text-copper hover:text-gold"
      >
        {t("ui:articles.relatedJobsCta")} ←
      </Link>
    </section>
  );
}

export default function ArticlePage() {
  const { slug } = useParams<{ slug: string }>();
  const article = slug ? getArticle(slug) : undefined;

  if (!article) {
    return (
      <div className="mx-auto max-w-2xl px-6 pt-24 pb-16">
        <SeoHead
          title="המאמר לא נמצא"
          description="המאמר המבוקש אינו זמין."
          canonical={`${SITE_URL}/articles`}
          noIndex
        />
        <p className="text-sm text-white/55">המאמר לא נמצא.</p>
        <Link
          to="/articles"
          className="mt-6 inline-block text-sm text-copper hover:text-gold"
        >
          ← כל המאמרים
        </Link>
      </div>
    );
  }

  const canonical = `${SITE_URL}/articles/${article.slug}`;
  const absoluteImage = article.image ? `${SITE_URL}${article.image}` : undefined;
  const articleSchema = {
    "@type": "Article",
    headline: article.title,
    description: article.description,
    datePublished: article.date,
    dateModified: article.date,
    inLanguage: "he-IL",
    mainEntityOfPage: canonical,
    author: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      logo: { "@type": "ImageObject", url: `${SITE_URL}/logo.svg` },
    },
    ...(absoluteImage ? { image: absoluteImage } : {}),
    ...(article.keywords ? { keywords: article.keywords } : {}),
  };
  const breadcrumb = {
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
      {
        "@type": "ListItem",
        position: 2,
        name: "מאמרים",
        item: `${SITE_URL}/articles`,
      },
      { "@type": "ListItem", position: 3, name: article.title, item: canonical },
    ],
  };
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [articleSchema, breadcrumb],
  };

  return (
    <div className="pt-16">
      <SeoHead
        title={article.title}
        description={article.description}
        canonical={canonical}
        ogType="article"
        ogImage={absoluteImage}
        structuredData={structuredData}
      />

      {/* Banner — full-bleed hero image with copper-tinted gradient overlay
          for legibility. Fades in once loaded so slow networks don't flash
          a broken-image placeholder. Falls through gracefully if no image. */}
      {article.image && (
        <div className="relative -mt-16 h-[280px] overflow-hidden bg-void sm:h-[360px]">
          <FadeInImage
            src={article.image}
            alt={article.imageAlt || article.title}
            className="absolute inset-0 h-full w-full object-cover"
            loading="eager"
            fadeMs={700}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-void/40 via-page/55 to-page" />
        </div>
      )}

      <div className="mx-auto max-w-2xl px-6 pb-16">
        <Link
          to="/articles"
          className={`${article.image ? "-mt-8 relative" : "mt-6"} mb-6 inline-flex items-center gap-1.5 text-sm text-white/45 transition hover:text-copper`}
        >
          ← כל המאמרים
        </Link>

        <article>
          <header className="mb-8">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/70">
              {formatDate(article.date)}
            </p>
            <h1 className="mt-3 text-2xl font-semibold text-white/95 sm:text-3xl">
              {article.title}
            </h1>
            <p className="mt-3 text-sm text-white/55 sm:text-base">
              {article.description}
            </p>
          </header>

          <div
            className="prose-article text-white/75"
            // Markdown is in-repo (not user input). Trusted source.
            dangerouslySetInnerHTML={{ __html: article.bodyHtml }}
          />

          <RelatedJobs />
        </article>
      </div>
    </div>
  );
}
